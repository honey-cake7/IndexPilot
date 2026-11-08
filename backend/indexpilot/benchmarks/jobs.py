from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from indexpilot.benchmarks.dataset import rebind_sql
from indexpilot.benchmarks.models import BenchmarkView, MeasurementView
from indexpilot.candidates.models import CandidateKey
from indexpilot.candidates.sql import definition
from indexpilot.errors import DomainError
from indexpilot.metadata.models import (
    BenchmarkCandidate,
    BenchmarkJob,
    BenchmarkMeasurement,
    BenchmarkQuery,
    BenchmarkSample,
    IndexCandidate,
    RecommendationQuery,
    RecommendationSet,
    RecommendationSetIndex,
)
from indexpilot.recommendations.service import validated_definition
from indexpilot.sql.models import SQLAnalysis


def view(row):
    return BenchmarkView(
        id=row.id,
        recommendation_id=row.recommendation_id,
        status=row.status,
        request=row.request,
        manifest=row.manifest,
        result=row.result,
        error_code=row.error_code,
        cleanup_confirmed=row.cleanup_confirmed,
        cancel_requested=row.cancel_requested,
        created_at=row.created_at.isoformat(),
        started_at=row.started_at.isoformat() if row.started_at else None,
        finished_at=row.finished_at.isoformat() if row.finished_at else None,
    )


def get_job(engine, identifier):
    with Session(engine) as db:
        row = db.get(BenchmarkJob, identifier)
        if row is None:
            raise DomainError("not_found", "Benchmark job was not found.", 404)
        return view(row)


def enqueue(engine, body):
    with Session(engine) as db, db.begin():
        db.execute(select(func.pg_advisory_xact_lock(918273647)))
        if (
            db.scalar(
                select(func.count())
                .select_from(BenchmarkJob)
                .where(BenchmarkJob.status.in_(["queued", "running"]))
            )
            >= 8
        ):
            raise DomainError("benchmark_queue_full", "The local benchmark queue is full.", 409)
        recommendation = db.get(RecommendationSet, body.recommendation_id)
        if recommendation is None:
            raise DomainError("not_found", "Recommendation was not found.", 404)
        queries = list(
            db.scalars(
                select(RecommendationQuery)
                .where(RecommendationQuery.recommendation_id == recommendation.id)
                .order_by(RecommendationQuery.source_plan_id)
            )
        )
        if (
            not 1 <= len(queries) <= 10
            or body.repetitions
            * 3
            * body.clients
            * body.transactions_per_client
            * (4 + len(queries))
            > 200000
        ):
            raise DomainError(
                "benchmark_limit",
                "Benchmark requires 1–10 queries and at most 200000 recorded transactions.",
            )
        row = BenchmarkJob(
            recommendation_id=recommendation.id,
            status="queued",
            request=body.model_dump(mode="json"),
            manifest={},
        )
        db.add(row)
        db.flush()
        tables = {}
        for query in queries:
            analysis = SQLAnalysis.model_validate(query.analysis)
            rebind_sql(analysis, "ipb_" + row.id.hex)
            tables.update({table.oid: table for table in analysis.tables})
            db.add(
                BenchmarkQuery(
                    job_id=row.id,
                    source_plan_id=query.source_plan_id,
                    frequency=query.frequency,
                    canonical_sql=analysis.canonical_sql,
                    analysis=query.analysis,
                )
            )
        selected = list(
            db.scalars(
                select(RecommendationSetIndex).where(
                    RecommendationSetIndex.recommendation_id == recommendation.id
                )
            )
        )
        selected_ids = {index.candidate_id for index in selected}
        batch_id = recommendation.provenance["batch_id"]
        import uuid

        candidates = {
            candidate.id: validated_definition(candidate, tables)
            for candidate in db.scalars(
                select(IndexCandidate).where(
                    IndexCandidate.batch_id == uuid.UUID(batch_id),
                    IndexCandidate.status == "proposed",
                    IndexCandidate.id.not_in(selected_ids),
                )
            )
        }
        for index in selected:
            model = index.definition
            rebuilt = definition(
                tables[model["table_oid"]],
                [CandidateKey.model_validate(key) for key in model["keys"]],
            )
            if rebuilt.model_dump(mode="json", exclude={"ddl"}) != model:
                raise DomainError(
                    "invalid_benchmark_source", "Saved selected definition is inconsistent.", 409
                )
            candidates[index.candidate_id] = rebuilt
        for identifier, candidate in candidates.items():
            if candidate.schema_name != "public" or candidate.table_name not in {
                "users",
                "products",
                "orders",
                "order_items",
                "payments",
            }:
                raise DomainError(
                    "unsupported_benchmark_candidate", "Only sample-table candidates are supported."
                )
            db.add(
                BenchmarkCandidate(
                    job_id=row.id,
                    candidate_id=identifier,
                    definition=candidate.model_dump(mode="json"),
                    selected=identifier in selected_ids,
                )
            )
        identifier = row.id
    return get_job(engine, identifier)


def cancel(engine, identifier):
    with Session(engine) as db, db.begin():
        row = db.scalar(select(BenchmarkJob).where(BenchmarkJob.id == identifier).with_for_update())
        if row is None:
            raise DomainError("not_found", "Benchmark job was not found.", 404)
        if row.status in ("queued", "running"):
            row.cancel_requested = True
            if row.status == "queued":
                row.status, row.cleanup_confirmed, row.finished_at = (
                    "cancelled",
                    True,
                    datetime.now(UTC),
                )
    return get_job(engine, identifier)


def list_jobs(engine, *, recommendation_id=None, limit=50, offset=0):
    with Session(engine) as db:
        query = select(BenchmarkJob)
        if recommendation_id is not None:
            query = query.where(BenchmarkJob.recommendation_id == recommendation_id)
        return [
            view(row)
            for row in db.scalars(
                query.order_by(BenchmarkJob.created_at.desc(), BenchmarkJob.id)
                .limit(limit)
                .offset(offset)
            )
        ]


def list_measurements(engine, identifier):
    get_job(engine, identifier)
    with Session(engine) as db:
        return [
            MeasurementView(
                id=row.id,
                repetition=row.repetition,
                arm=row.arm,
                phase=row.phase,
                metrics=row.metrics,
                conditions=row.conditions,
            )
            for row in db.scalars(
                select(BenchmarkMeasurement)
                .where(BenchmarkMeasurement.job_id == identifier)
                .order_by(
                    BenchmarkMeasurement.repetition,
                    BenchmarkMeasurement.arm,
                    BenchmarkMeasurement.phase,
                )
            )
        ]


def samples(engine, measurement_id, *, limit=100, offset=0):
    with Session(engine) as db:
        if db.get(BenchmarkMeasurement, measurement_id) is None:
            raise DomainError("not_found", "Measurement was not found.", 404)
        return [
            dict(
                client_id=row.client_id,
                sequence=row.sequence,
                script_id=row.script_id,
                latency_us=row.latency_us,
            )
            for row in db.scalars(
                select(BenchmarkSample)
                .where(BenchmarkSample.measurement_id == measurement_id)
                .order_by(BenchmarkSample.client_id, BenchmarkSample.sequence)
                .limit(limit)
                .offset(offset)
            )
        ]
