import uuid

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from indexpilot.candidates.generator import CandidateSource, generate_candidates
from indexpilot.candidates.models import (
    CandidateBatchSummary,
    CandidateBatchView,
    CandidateRequest,
    CandidateView,
    GenerationOptions,
)
from indexpilot.candidates.sql import load_operator_classes
from indexpilot.config import Settings
from indexpilot.db.connections import require_demo_identity, target_connection
from indexpilot.errors import DomainError
from indexpilot.metadata.models import (
    CandidateBatch,
    CandidateBatchSource,
    IndexCandidate,
    IndexCandidateEvidence,
    PlanAnalysis,
)
from indexpilot.metadata.targets import ensure_demo_target
from indexpilot.sql.models import SQLAnalysis
from indexpilot.sql.safety import require_safe_table


def create_batch(engine: Engine, settings: Settings, body: CandidateRequest):
    with Session(engine) as session, session.begin():
        target_id = ensure_demo_target(session, settings)
        rows = list(session.scalars(select(PlanAnalysis).where(PlanAnalysis.id.in_(body.plan_ids))))
        if len(rows) != len(body.plan_ids):
            raise DomainError("not_found", "A requested source plan was not found.", 404)
        if any(row.database_id != target_id for row in rows):
            raise DomainError(
                "different_targets", "All source plans must belong to the configured demo target."
            )
        sources = [
            CandidateSource(row.id, SQLAnalysis.model_validate(row.analysis)) for row in rows
        ]
    tables = {}
    with target_connection(settings) as connection:
        require_demo_identity(connection)
        for source in sources:
            for observed in source.analysis.tables:
                if observed.oid not in tables:
                    try:
                        current = require_safe_table(
                            connection,
                            observed.schema_name,
                            observed.name,
                            allowed_schemas=settings.analysis_schemas,
                        )
                    except DomainError as error:
                        if error.code == "relation_not_found":
                            raise DomainError(
                                "stale_plan",
                                "Source relation is absent; analyze the query again.",
                                409,
                            ) from None
                        raise
                    if current.oid != observed.oid:
                        raise DomainError(
                            "stale_plan", "Table identity changed; analyze the query again.", 409
                        )
                    tables[current.oid] = current
                current = tables[observed.oid]
                if (current.schema_name, current.name) != (observed.schema_name, observed.name):
                    raise DomainError(
                        "stale_plan", "Source relation was renamed; analyze the query again.", 409
                    )
                current_columns = {column.name: column for column in current.columns}
                for usage in source.analysis.columns:
                    if usage.column.relation_oid != observed.oid:
                        continue
                    old = next(
                        (column for column in observed.columns if column.name == usage.column.name),
                        None,
                    )
                    new = current_columns.get(usage.column.name)
                    if (
                        old is None
                        or new is None
                        or (old.number, old.type_oid, old.collation_oid)
                        != (
                            new.number,
                            new.type_oid,
                            new.collation_oid,
                        )
                    ):
                        raise DomainError(
                            "stale_plan",
                            "Referenced columns changed; analyze the query again.",
                            409,
                        )
        classes = load_operator_classes(connection)
        observed_at = connection.execute("SELECT clock_timestamp()").fetchone()[0]
    options = GenerationOptions(max_columns=body.max_columns, max_candidates=body.max_candidates)
    result = generate_candidates(sources, tables, classes, options)
    with Session(engine) as session, session.begin():
        batch = CandidateBatch(
            database_id=target_id,
            catalog_observed_at=observed_at,
            options=options.model_dump(),
            algorithm_version="btree-patterns-v1",
            attempts=result.attempts,
            unique_considered=result.unique_considered,
            search_truncated=result.search_truncated,
            warnings=result.warnings,
        )
        session.add(batch)
        session.flush()
        session.add_all(
            CandidateBatchSource(batch_id=batch.id, plan_id=source.plan_id) for source in sources
        )
        evidence_rows = []
        for decision in [*result.proposed, *result.rejected]:
            data = decision.model_dump(
                mode="json",
                exclude={
                    "evaluation_status",
                    "estimated_size_bytes",
                    "estimated_improvement_pct",
                    "evidence",
                },
            )
            candidate = IndexCandidate(
                id=uuid.uuid4(), batch_id=batch.id, signature=decision.definition.signature, **data
            )
            session.add(candidate)
            evidence_rows.extend(
                IndexCandidateEvidence(
                    candidate_id=candidate.id,
                    plan_id=item.plan_id,
                    query_alias=item.alias,
                    reason=item.reason,
                    explanation=item.explanation,
                )
                for item in decision.evidence
            )
        session.flush()
        session.add_all(evidence_rows)
        identifier = batch.id
    return get_batch(engine, identifier)


def get_batch(engine: Engine, identifier: uuid.UUID):
    with Session(engine) as session:
        batch = session.get(CandidateBatch, identifier)
        if batch is None:
            raise DomainError("not_found", "Candidate batch was not found.", 404)
        plan_ids = list(
            session.scalars(
                select(CandidateBatchSource.plan_id)
                .where(
                    CandidateBatchSource.batch_id == identifier,
                )
                .order_by(CandidateBatchSource.plan_id)
            )
        )
        rows = list(
            session.scalars(
                select(IndexCandidate)
                .where(IndexCandidate.batch_id == identifier)
                .order_by(IndexCandidate.signature)
            )
        )
        evidence = list(
            session.scalars(
                select(IndexCandidateEvidence)
                .where(
                    IndexCandidateEvidence.candidate_id.in_([row.id for row in rows]),
                )
                .order_by(
                    IndexCandidateEvidence.plan_id,
                    IndexCandidateEvidence.query_alias,
                    IndexCandidateEvidence.reason,
                )
            )
        )
        views = [
            CandidateView(
                id=row.id,
                definition=row.definition,
                status=row.status,
                rejection_reason=row.rejection_reason,
                existing_indexes=row.existing_indexes,
                warnings=row.warnings,
                evidence=[
                    dict(
                        plan_id=item.plan_id,
                        alias=item.query_alias,
                        reason=item.reason,
                        explanation=item.explanation,
                    )
                    for item in evidence
                    if item.candidate_id == row.id
                ],
            )
            for row in rows
        ]
        return CandidateBatchView(
            id=batch.id,
            created_at=batch.created_at,
            catalog_observed_at=batch.catalog_observed_at,
            source_plan_ids=plan_ids,
            options=batch.options,
            proposed=[view for view in views if view.status == "proposed"],
            rejected=[view for view in views if view.status == "rejected"],
            attempts=batch.attempts,
            unique_considered=batch.unique_considered,
            search_truncated=batch.search_truncated,
            warnings=batch.warnings,
        )


def list_batches(engine: Engine, *, limit=50, offset=0):
    with Session(engine) as session:
        rows = session.scalars(
            select(CandidateBatch)
            .order_by(CandidateBatch.created_at.desc(), CandidateBatch.id)
            .offset(offset)
            .limit(limit)
        )
        return [CandidateBatchSummary.model_validate(row, from_attributes=True) for row in rows]
