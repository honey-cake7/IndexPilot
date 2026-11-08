import math

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from indexpilot.candidates.models import CandidateDefinition, CandidateEvidence
from indexpilot.candidates.sql import definition as compile_definition
from indexpilot.errors import DomainError
from indexpilot.evaluation.costs import weighted_cost
from indexpilot.evaluation.persistence import get_run
from indexpilot.metadata.models import (
    CandidateBatch,
    EvaluationQuery,
    IndexCandidate,
    IndexCandidateEvidence,
    OptimizationRun,
    OptimizationTrial,
    PlanAnalysis,
    RecommendationIndexQuery,
    RecommendationQuery,
    RecommendationSet,
    RecommendationSetIndex,
)
from indexpilot.optimizer.persistence import get_optimization
from indexpilot.recommendations.explain import (
    VERSION,
    index_explanation,
    invalid_source,
    query_explanation,
    summary,
)
from indexpilot.recommendations.persistence import get_recommendation


def validated_definition(row, tables):
    try:
        candidate = CandidateDefinition.model_validate(row.definition)
        table = tables[candidate.table_oid]
        columns = {column.name: column for column in table.columns}
        if not 1 <= len(candidate.keys) <= 3 or len({key.column for key in candidate.keys}) != len(
            candidate.keys
        ):
            raise ValueError("Invalid keys")
        for key in candidate.keys:
            column = columns[key.column]
            if (column.number, column.type_oid, column.collation_oid) != (
                key.attribute_number,
                key.type_oid,
                key.collation_oid,
            ):
                raise ValueError("Column differs")
        rebuilt = compile_definition(table, candidate.keys)
        if rebuilt != candidate or candidate.signature != row.signature:
            raise ValueError("Definition differs")
        return rebuilt
    except (ValidationError, KeyError, ValueError, TypeError):
        raise invalid_source() from None


def freeze(db, source_row):
    connection = db.connection()
    optimization = get_optimization(connection, source_row.id)
    evidence = get_run(connection, optimization.evaluation_run_id)
    result = optimization.result
    selected = result.selected_candidate_ids
    before = {query.source_plan_id: query for query in result.baseline.queries}
    after = {query.source_plan_id: query for query in result.final.queries}
    contexts = {query.source_plan_id: query for query in evidence.queries}
    members = {index.candidate_id: index for index in result.final.indexes}
    chosen = sorted(
        [trial for trial in result.trials if trial.chosen], key=lambda trial: trial.step
    )
    if (
        not evidence.cleanup_confirmed
        or evidence.status != "completed"
        or set(before) != set(after)
        or set(before) != set(contexts)
        or not before
        or len(set(selected)) != len(selected)
        or set(selected) != set(members)
        or [trial.added_candidate_id for trial in chosen] != selected
    ):
        raise invalid_source()
    for estimate, score in [
        (result.baseline, result.baseline_score),
        (result.final, result.final_score),
    ]:
        cost = weighted_cost(
            (query.frequency, query.plan.root.total_cost) for query in estimate.queries
        )
        if (
            cost is None
            or score.read_cost is None
            or not math.isclose(cost, score.read_cost, rel_tol=1e-12)
        ):
            raise invalid_source()
    size = sum(index.estimated_size_bytes or 0 for index in members.values())
    if (
        any(
            index.estimated_size_bytes is None or index.estimated_size_bytes <= 0
            for index in members.values()
        )
        or size != result.final_score.storage_bytes
        or size > optimization.options.storage_budget_bytes
    ):
        raise invalid_source()
    batch = db.get(CandidateBatch, optimization.batch_id)
    run = RecommendationSet(
        optimization_id=optimization.id,
        explanation_version=VERSION,
        provenance={
            "optimization_id": str(optimization.id),
            "optimization_created_at": optimization.created_at.isoformat(),
            "evaluation_run_id": str(evidence.id),
            "evaluation_created_at": evidence.created_at.isoformat(),
            "batch_id": str(batch.id),
            "generation_algorithm": batch.algorithm_version,
            "generation_options": batch.options,
            "generation_truncated": batch.search_truncated,
            "generation_catalog_observed_at": batch.catalog_observed_at.isoformat(),
            "selection_algorithm": result.algorithm,
            "evaluation_context": evidence.context,
            "hypopg_capability": evidence.capability.model_dump(),
        },
        options=optimization.options.model_dump(mode="json"),
        summary=summary(result, optimization.options).model_dump(mode="json"),
        warnings=list(
            dict.fromkeys(
                [
                    *result.warnings,
                    *batch.warnings,
                    "Historical snapshot; current target schema/statistics were not rechecked.",
                    "Query contributions describe the final set, not independent index gains.",
                    "Execution/write performance is unmeasured; benchmark outcome is unavailable.",
                ]
            )
        ),
    )
    db.add(run)
    db.flush()
    query_rows = list(
        db.scalars(select(EvaluationQuery).where(EvaluationQuery.run_id == evidence.id))
    )
    source_queries = {row.source_plan_id: row for row in query_rows}
    for identifier, context in contexts.items():
        original = db.get(PlanAnalysis, identifier)
        db.add(
            RecommendationQuery(
                recommendation_id=run.id,
                source_plan_id=identifier,
                evaluation_query_id=source_queries[identifier].id,
                frequency=context.frequency,
                original_sql=original.original_sql,
                analysis=context.analysis.model_dump(mode="json"),
                baseline_raw_explain=before[identifier].raw_explain,
                hypothetical_raw_explain=after[identifier].raw_explain,
                explanation=query_explanation(
                    before[identifier],
                    after[identifier],
                    context.analysis,
                    result.baseline_score.read_cost,
                ).model_dump(mode="json"),
            )
        )
    tables = {
        table.oid: table for context in contexts.values() for table in context.analysis.tables
    }
    previous = result.baseline_score
    previous_ids = set()
    for number, trial in enumerate(chosen, 1):
        identifier = trial.added_candidate_id
        previous_ids.add(identifier)
        if trial.step != number or set(trial.candidate_ids) != previous_ids:
            raise invalid_source()
        row = db.get(IndexCandidate, identifier)
        if row is None or row.batch_id != batch.id or row.status != "proposed":
            raise invalid_source()
        candidate = validated_definition(row, tables)
        source_trial = db.scalar(
            select(OptimizationTrial).where(
                OptimizationTrial.run_id == optimization.id,
                OptimizationTrial.chosen.is_(True),
                OptimizationTrial.step == number,
                OptimizationTrial.added_candidate_id == identifier,
            )
        )
        if source_trial is None:
            raise invalid_source()
        reasons = list(
            db.scalars(
                select(IndexCandidateEvidence)
                .where(IndexCandidateEvidence.candidate_id == identifier)
                .order_by(
                    IndexCandidateEvidence.plan_id,
                    IndexCandidateEvidence.query_alias,
                    IndexCandidateEvidence.reason,
                )
            )
        )
        if any(reason.plan_id not in contexts for reason in reasons):
            raise invalid_source()
        used = {key for key, query in after.items() if identifier in query.used_candidate_ids}
        db.add(
            RecommendationSetIndex(
                recommendation_id=run.id,
                candidate_id=identifier,
                selection_order=number,
                source_trial_id=source_trial.id,
                definition=candidate.model_dump(mode="json", exclude={"ddl"}),
                estimated_size_bytes=members[identifier].estimated_size_bytes,
                explanation=index_explanation(trial, previous, used).model_dump(mode="json"),
                deployment_sql=candidate.ddl + ";",
            )
        )
        db.flush()
        for key in sorted(used | {reason.plan_id for reason in reasons}, key=str):
            db.add(
                RecommendationIndexQuery(
                    recommendation_id=run.id,
                    candidate_id=identifier,
                    source_plan_id=key,
                    proposed_evidence=[
                        CandidateEvidence(
                            plan_id=reason.plan_id,
                            alias=reason.query_alias,
                            reason=reason.reason,
                            explanation=reason.explanation,
                        ).model_dump(mode="json")
                        for reason in reasons
                        if reason.plan_id == key
                    ],
                    used_in_final_plan=key in used,
                )
            )
        previous = trial.score
    return run.id


def create_recommendation(engine, body):
    with Session(engine) as db, db.begin():
        # Serialize only snapshot creation for this optimization; duplicate requests reuse it.
        source = db.scalar(
            select(OptimizationRun)
            .where(OptimizationRun.id == body.optimization_id)
            .with_for_update()
        )
        if source is None:
            raise DomainError("not_found", "Optimization was not found.", 404)
        existing = db.scalar(
            select(RecommendationSet.id).where(RecommendationSet.optimization_id == source.id)
        )
        created = existing is None
        identifier = freeze(db, source) if created else existing
    return get_recommendation(engine, identifier), created
