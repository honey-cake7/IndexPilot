import psycopg
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from indexpilot.config import Settings
from indexpilot.db.connections import require_demo_identity, target_connection
from indexpilot.errors import DomainError
from indexpilot.evaluation.context import SourceQuery, prepare_context
from indexpilot.evaluation.engine import EvaluationBudget, WorkloadEvaluator
from indexpilot.evaluation.models import HypoPGCapability
from indexpilot.evaluation.persistence import save_run
from indexpilot.evaluation.session import HypoPGUnavailable, HypotheticalSession
from indexpilot.local import LocalConnectionError
from indexpilot.metadata.models import (
    CandidateBatch,
    CandidateBatchSource,
    IndexCandidate,
    PlanAnalysis,
)
from indexpilot.metadata.targets import ensure_demo_target
from indexpilot.sql.models import SQLAnalysis


def load_request(engine, settings, body):
    with Session(engine) as db, db.begin():
        batch = db.get(CandidateBatch, body.batch_id)
        if batch is None:
            raise DomainError("not_found", "Candidate batch was not found.", 404)
        if batch.database_id != ensure_demo_target(db, settings):
            raise DomainError("different_targets", "The batch belongs to a different target.")
        rows = list(
            db.scalars(
                select(IndexCandidate).where(
                    IndexCandidate.batch_id == body.batch_id, IndexCandidate.status == "proposed"
                )
            )
        )
        proposed = {row.id: row.definition for row in rows}
        if any(row.signature != row.definition.get("signature") for row in rows):
            raise DomainError(
                "invalid_candidate", "Saved candidate signature is inconsistent.", 409
            )
        if body.candidate_sets is None:
            ids = sorted(proposed, key=str)
            groups = [[identifier] for identifier in ids]
            if len(ids) > 1:
                groups.append(ids)
        else:
            groups = [sorted(group, key=str) for group in body.candidate_sets]
        requested = {identifier for group in groups for identifier in group}
        if requested - proposed.keys():
            raise DomainError(
                "invalid_candidate_set",
                "Each set must contain proposed candidates from this batch.",
            )
        plans = list(
            db.scalars(
                select(PlanAnalysis)
                .join(CandidateBatchSource, CandidateBatchSource.plan_id == PlanAnalysis.id)
                .where(CandidateBatchSource.batch_id == body.batch_id)
                .order_by(PlanAnalysis.id)
            )
        )
        if not 1 <= len(plans) <= 100:
            raise DomainError(
                "invalid_batch", "Batch source-query count is outside supported limits.", 409
            )
        try:
            sources = [
                SourceQuery(row.id, row.frequency, SQLAnalysis.model_validate(row.analysis))
                for row in plans
            ]
        except ValidationError:
            raise DomainError(
                "invalid_source_plan", "Saved plan context is invalid; analyze it again.", 409
            ) from None
    return sources, {identifier: proposed[identifier] for identifier in requested}, groups


def evaluate_batch(engine, settings: Settings, body):
    sources, stored, groups = load_request(engine, settings, body)
    context = {
        "policy": "hypopg-sets-v1",
        "planning_budget_seconds": settings.evaluation_timeout_seconds,
        "max_sets": 64,
        "snapshot_policy": "repeatable-read-read-only",
    }
    capability = HypoPGCapability(available=False)
    hypo = None
    queries = []
    results = []
    error = None
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
                    "unsupported_version", "Hypothetical evaluation requires PostgreSQL 18.", 503
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
                evaluator = WorkloadEvaluator(connection, hypo, queries, compiled, budget)
                context["planner_settings"] = evaluator.settings
                results.append(evaluator.evaluate())
                for group in groups:
                    results.append(evaluator.evaluate(frozenset(group)))
    except HypoPGUnavailable as failure:
        capability = failure.capability
        status = "unavailable"
        warnings = [failure.message]
        results = []
    except (DomainError, LocalConnectionError, psycopg.Error) as failure:
        status = "failed"
        results = []
        if isinstance(failure, DomainError):
            error = failure
        elif isinstance(failure, LocalConnectionError):
            error = DomainError(failure.code, str(failure), 503)
        else:
            code, status_code = (
                ("statement_timeout", 504)
                if failure.sqlstate == "57014"
                else (
                    ("insufficient_privilege", 403)
                    if failure.sqlstate == "42501"
                    else ("database_error", 503)
                )
            )
            error = DomainError(code, "Hypothetical evaluation failed in PostgreSQL.", status_code)
        warnings = ["The evaluation failed; partial trial results were not published."]
    else:
        status = "completed"
        warnings = [
            "Hypothetical costs and storage are estimates; execution performance is unmeasured.",
            "Combined sets were replanned directly; singleton benefits were not added together.",
        ]
    if hypo:
        capability = hypo.capability
    run = save_run(
        engine,
        batch_id=body.batch_id,
        status=status,
        capability=capability,
        requested_sets=groups,
        context=context,
        queries=queries if status == "completed" else [],
        results=results,
        warnings=warnings,
        error_code=error.code
        if error
        else ("hypopg_unavailable" if status == "unavailable" else None),
        cleanup_confirmed=hypo.cleanup_confirmed if hypo else False,
    )
    if error:
        raise DomainError(
            error.code, f"{error.message} Saved evaluation ID: {run.id}.", error.status
        ) from None
    return run
