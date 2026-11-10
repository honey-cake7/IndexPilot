import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from indexpilot.benchmarks.jobs import get_job, list_measurements
from indexpilot.candidates.service import get_batch
from indexpilot.errors import DomainError
from indexpilot.metadata.models import SavedReport
from indexpilot.optimizer.persistence import get_optimization
from indexpilot.recommendations.persistence import deployment_sql, get_recommendation
from indexpilot.reports.models import (
    VERSION,
    ReportBenchmark,
    ReportCandidate,
    ReportComparison,
    ReportDocument,
    ReportIndex,
    ReportMeasurement,
    ReportMetrics,
    ReportPage,
    ReportPolicy,
    ReportQuery,
    ReportRequest,
    ReportSummary,
)

# Explicit allowlists exclude credentials, hosts, raw SQL/plans and future private
# fields from generic provenance/worker dictionaries. No target connection occurs.
CONTEXT_KEYS = (
    "database",
    "database_oid",
    "server_version",
    "planner_settings",
    "policy",
    "snapshot_policy",
    "frequency_basis",
    "catalog_observed_at",
    "planning_budget_seconds",
    "max_evaluations",
)
CONDITION_KEYS = (
    "dataset",
    "seed",
    "clients",
    "threads",
    "protocol",
    "read_warmup_per_client",
    "transaction_definition",
    "additional_index_bytes",
    "actual_budget_fit",
    "total_index_bytes",
    "additional_index_bytes_after",
    "actual_budget_fit_after",
    "orders_after",
    "returning_row_checked",
)
MANIFEST_KEYS = (
    "server_version",
    "pgbench_version",
    "cache_policy",
    "dataset",
    "seed",
    "orders",
    "arm_order",
    "rotation",
    "storage_budget_bytes",
    "budget_bytes",
    "read_weights",
    "weight_policy",
    "sample_semantics",
    "planner_settings",
    "protocol",
    "threads",
    "client_platform",
    "python_version",
    "host_cpu_count",
    "container_limits",
    "policy",
)
REQUEST_KEYS = (
    "orders",
    "seed",
    "clients",
    "repetitions",
    "transactions_per_client",
    "read_warmup_per_client",
    "timeout_seconds",
    "regression_threshold_pct",
)


def project(source, keys):
    return {key: source[key] for key in keys if key in source}


def freeze_benchmark(connection, identifier, recommendation_id):
    job = get_job(connection, identifier)
    if job.recommendation_id != recommendation_id:
        raise DomainError(
            "report_benchmark_mismatch",
            "Choose benchmark jobs belonging to this recommendation.",
            422,
        )
    if job.status in ("queued", "running"):
        raise DomainError(
            "report_benchmark_active",
            "Wait for the selected benchmark to finish, or cancel it before creating a report.",
            409,
        )
    result = job.result or {}
    measurements = list_measurements(connection, identifier)
    complete = (
        job.status == "completed"
        and job.cleanup_confirmed
        and bool(result.get("comparisons"))
        and bool(measurements)
    )
    return ReportBenchmark(
        id=job.id,
        status=job.status,
        cleanup_confirmed=job.cleanup_confirmed,
        complete_comparison=complete,
        created_at=job.created_at,
        finished_at=job.finished_at,
        error_code=job.error_code,
        request=project(job.request, REQUEST_KEYS),
        conditions=project(job.manifest, MANIFEST_KEYS),
        measurements=[
            ReportMeasurement(
                id=m.id,
                repetition=m.repetition,
                arm=m.arm,
                phase=m.phase,
                metrics=ReportMetrics.model_validate(m.metrics),
                conditions=project(m.conditions, CONDITION_KEYS),
            )
            for m in measurements
        ],
        comparisons=[ReportComparison.model_validate(c) for c in result.get("comparisons", [])]
        if complete
        else [],
        warnings=result.get("warnings", [])
        if complete
        else ["Partial measurements are not a completed comparison."],
    )


def create_report(engine, body: ReportRequest):
    # All source reads and the insert share one MVCC snapshot/transaction. Reports
    # are explicit frozen projections, never live joins at download time.
    with (
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection,
        connection.begin(),
    ):
        rec = get_recommendation(connection, body.recommendation_id)
        opt = get_optimization(connection, rec.optimization_id)
        batch = get_batch(connection, opt.batch_id)
        sql = {s.candidate_id: s.sql for s in deployment_sql(connection, rec.id).statements}
        outcomes = {c.candidate_id: c for c in opt.result.candidates}
        benchmarks = [freeze_benchmark(connection, b, rec.id) for b in body.benchmark_ids]
        missing = []
        if not benchmarks:
            missing.append(
                "No physical benchmark was selected; runtime and write performance "
                "are unmeasured in this report."
            )
        for b in benchmarks:
            if not b.complete_comparison:
                missing.append(
                    f"Benchmark {b.id} is {b.status}; a completed, cleanup-verified "
                    "comparison is unavailable."
                )
        missing.extend(
            [
                "Cold-cache, WAL and statistical significance were not measured.",
                "Greedy selection does not establish a global optimum.",
            ]
        )
        document = ReportDocument(
            id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            title=body.title,
            recommendation_id=rec.id,
            optimization_id=opt.id,
            batch_id=opt.batch_id,
            policy=ReportPolicy(
                original_sql_included=body.include_original_sql,
                representative_sql_included=body.include_representative_sql,
                parameter_policy="Original SQL can contain literals. Bound representative SQL "
                "is included by explicit request."
                if body.include_representative_sql
                else "Bound representative SQL, raw plans and typed parameter maps are omitted. "
                "Original SQL may still contain literal values.",
            ),
            summary=rec.summary,
            settings=rec.options,
            provenance={
                "recommendation_created_at": rec.created_at.isoformat(),
                "optimization_created_at": opt.created_at.isoformat(),
                "explanation_version": rec.explanation_version,
                "selection_algorithm": opt.result.algorithm,
                "generation_options": batch.options.model_dump(mode="json"),
                "generation_truncated": batch.search_truncated,
                "evaluation_context": project(
                    rec.provenance.get("evaluation_context", {}), CONTEXT_KEYS
                ),
            },
            queries=[
                ReportQuery(
                    source_plan_id=q.source_plan_id,
                    frequency=q.frequency,
                    original_sql=q.original_sql if body.include_original_sql else None,
                    representative_sql=q.representative_sql
                    if body.include_representative_sql
                    else None,
                    explanation=q.explanation,
                    statistics=q.statistics_observations,
                )
                for q in rec.queries
            ],
            indexes=[
                ReportIndex(
                    candidate_id=i.candidate_id,
                    schema_name=i.definition.schema_name,
                    table_name=i.definition.table_name,
                    index_name=i.definition.index_name,
                    keys=i.definition.keys,
                    estimated_size_bytes=i.estimated_size_bytes,
                    explanation=i.explanation,
                    deployment_sql=sql[i.candidate_id] if body.include_original_sql else None,
                )
                for i in rec.indexes
            ],
            candidates=[
                ReportCandidate(
                    candidate_id=c.id,
                    schema_name=c.definition.schema_name,
                    table_name=c.definition.table_name,
                    keys=c.definition.keys,
                    generation_status=c.status,
                    selected=outcomes[c.id].selected if c.id in outcomes else False,
                    reason=c.rejection_reason
                    or (
                        outcomes[c.id].reason
                        if c.id in outcomes
                        else "Not evaluated in the saved optimization."
                    ),
                )
                for c in [*batch.proposed, *batch.rejected]
            ],
            search_trials=opt.result.trials,
            benchmarks=benchmarks,
            missing_evidence=missing,
            warnings=[
                *("Recommendation snapshot: " + warning for warning in rec.warnings),
                "Frozen historical evidence; current target conditions were not rechecked.",
                "Deployment SQL is for review only and was not executed on the monitored target.",
            ],
        )
        if len(document.model_dump_json().encode("utf-8")) > 4 * 1024 * 1024:
            raise DomainError(
                "report_too_large",
                "Choose fewer benchmark jobs or omit SQL to keep the report below 4 MiB.",
                422,
            )
        with Session(connection) as db, db.begin():
            db.add(
                SavedReport(
                    id=document.id,
                    recommendation_id=rec.id,
                    created_at=document.created_at,
                    title=document.title,
                    format_version=VERSION,
                    document=document.model_dump(mode="json"),
                )
            )
    return document


def get_report(engine, identifier):
    with Session(engine) as db:
        row = db.get(SavedReport, identifier)
        if row is None:
            raise DomainError(
                "not_found",
                "Report was not found. Choose a saved report or create one from a recommendation.",
                404,
            )
        return ReportDocument.model_validate(row.document)


def list_reports(engine, *, recommendation_id=None, q="", limit=20, offset=0):
    statement = select(SavedReport)
    if recommendation_id is not None:
        statement = statement.where(SavedReport.recommendation_id == recommendation_id)
    if q:
        statement = statement.where(SavedReport.title.icontains(q, autoescape=True))
    with (
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection,
        connection.begin(),
        Session(connection) as db,
    ):
        total = db.scalar(select(func.count()).select_from(statement.subquery()))
        items = db.scalars(
            statement.order_by(SavedReport.created_at.desc(), SavedReport.id)
            .limit(limit)
            .offset(offset)
        )
        return ReportPage(
            items=[ReportSummary.model_validate(row, from_attributes=True) for row in items],
            total=total,
            limit=limit,
            offset=offset,
        )
