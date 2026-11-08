import psycopg

from indexpilot.db.connections import require_demo_identity, target_connection
from indexpilot.errors import DomainError
from indexpilot.evaluation.context import prepare_context
from indexpilot.evaluation.engine import EvaluationBudget, WorkloadEvaluator
from indexpilot.evaluation.models import EvaluationRequest, HypoPGCapability
from indexpilot.evaluation.persistence import save_run
from indexpilot.evaluation.service import load_request
from indexpilot.evaluation.session import HypoPGUnavailable, HypotheticalSession
from indexpilot.local import LocalConnectionError
from indexpilot.optimizer.greedy import optimize
from indexpilot.optimizer.models import OptimizationOptions, SearchCandidate
from indexpilot.optimizer.persistence import save_optimization


class RecordedEvaluator:
    """Retain one normalized plan bundle per set; refresh replaces the same set's evidence."""

    def __init__(self, evaluator):
        self.evaluator = evaluator
        self.results = {}

    def evaluate(self, candidate_ids=frozenset(), *, refresh=False):
        result = self.evaluator.evaluate(candidate_ids, refresh=refresh)
        self.results[frozenset(candidate_ids)] = result.model_copy(deep=True)
        return result


def optimize_batch(engine, settings, body):
    sources, stored, _ = load_request(engine, settings, EvaluationRequest(batch_id=body.batch_id))
    options = OptimizationOptions.model_validate(body.model_dump(exclude={"batch_id"}))
    if options.write_weights.keys() - stored.keys():
        raise DomainError(
            "invalid_write_weights", "Write weights must reference proposed batch candidates."
        )
    context = {
        "policy": "greedy-marginal-v1",
        "snapshot_policy": "repeatable-read-read-only",
        "planning_budget_seconds": settings.evaluation_timeout_seconds,
        "max_evaluations": options.max_evaluations,
        "frequency_basis": options.frequency_basis,
    }
    capability = HypoPGCapability(available=False)
    hypo = None
    try:
        with target_connection(settings, repeatable_read=True) as connection:
            require_demo_identity(connection)
            database, oid, version, number, pid = connection.execute(
                "SELECT current_database(),oid::bigint,current_setting('server_version'), "
                "current_setting('server_version_num')::int,pg_backend_pid() "
                "FROM pg_database WHERE datname=current_database()"
            ).fetchone()
            context.update(
                database=database, database_oid=oid, server_version=version, backend_pid=pid
            )
            if not 180000 <= number < 190000:
                raise DomainError(
                    "unsupported_version", "Optimization requires PostgreSQL 18.", 503
                )
            hypo = HypotheticalSession(connection)
            with hypo:
                capability = hypo.capability
                budget = EvaluationBudget(
                    connection,
                    seconds=settings.evaluation_timeout_seconds,
                    statement_timeout_ms=settings.statement_timeout_ms,
                )
                queries, compiled = prepare_context(
                    connection,
                    sources,
                    stored,
                    allowed_schemas=settings.analysis_schemas,
                    check=budget.check,
                )
                context["catalog_observed_at"] = (
                    connection.execute("SELECT clock_timestamp()").fetchone()[0].isoformat()
                )
                evaluator = WorkloadEvaluator(
                    connection,
                    hypo,
                    queries,
                    compiled,
                    budget,
                    max_sets=options.max_evaluations,
                )
                context["planner_settings"] = evaluator.settings
                recorded = RecordedEvaluator(evaluator)
                result = optimize(
                    recorded,
                    [
                        SearchCandidate(id=identifier, signature=value.signature)
                        for identifier, value in compiled.items()
                    ],
                    options,
                )
    except (DomainError, LocalConnectionError, psycopg.Error) as failure:
        if isinstance(failure, HypoPGUnavailable):
            capability = failure.capability
            status, error = "unavailable", failure
        elif isinstance(failure, DomainError):
            status, error = "failed", failure
        elif isinstance(failure, LocalConnectionError):
            status, error = "failed", DomainError(failure.code, str(failure), 503)
        else:
            status = "failed"
            code, response_status = (
                ("statement_timeout", 504)
                if failure.sqlstate == "57014"
                else (
                    ("insufficient_privilege", 403)
                    if failure.sqlstate == "42501"
                    else ("database_error", 503)
                )
            )
            error = DomainError(code, "Optimization failed in PostgreSQL.", response_status)
        failed = save_run(
            engine,
            batch_id=body.batch_id,
            status=status,
            capability=hypo.capability if hypo else capability,
            requested_sets=[],
            context=context,
            queries=[],
            results=[],
            warnings=["Optimization failed; no partial selection or trial comparisons were saved."],
            error_code=error.code,
            cleanup_confirmed=hypo.cleanup_confirmed if hypo else False,
        )
        raise DomainError(
            error.code, f"{error.message} Saved evaluation ID: {failed.id}.", error.status
        ) from None
    return save_optimization(
        engine,
        result=result,
        options=options,
        evidence=dict(
            batch_id=body.batch_id,
            status="completed",
            capability=capability,
            requested_sets=[sorted(ids, key=str) for ids in recorded.results if ids],
            context=context,
            queries=queries,
            results=list(recorded.results.values()),
            warnings=result.warnings,
            error_code=None,
            cleanup_confirmed=hypo.cleanup_confirmed,
        ),
    )
