import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from indexpilot.errors import DomainError
from indexpilot.evaluation.costs import cost_reduction
from indexpilot.evaluation.models import (
    EvaluationQueryView,
    EvaluationRunView,
    EvaluationSummary,
    IndexEstimate,
    QueryEstimate,
    SetEstimate,
)
from indexpilot.metadata.models import (
    EvaluationMember,
    EvaluationPlan,
    EvaluationQuery,
    EvaluationRun,
    IndexEvaluation,
)
from indexpilot.plans.explanations import explain_plan
from indexpilot.plans.parser import parse_explain, walk_plan
from indexpilot.sql.models import SQLAnalysis


def save_run(
    engine,
    *,
    batch_id,
    status,
    capability,
    requested_sets,
    context,
    queries,
    results,
    warnings,
    error_code,
    cleanup_confirmed,
):
    with Session(engine) as db, db.begin():
        run = EvaluationRun(
            batch_id=batch_id,
            status=status,
            capability=capability.model_dump(),
            requested_sets=[[str(identifier) for identifier in group] for group in requested_sets],
            context=context,
            warnings=warnings,
            error_code=error_code,
            cleanup_confirmed=cleanup_confirmed,
        )
        db.add(run)
        db.flush()
        query_ids = {}
        for query in queries:
            row = EvaluationQuery(
                run_id=run.id,
                source_plan_id=query.source_plan_id,
                frequency=query.frequency,
                analysis=query.analysis.model_dump(mode="json"),
            )
            db.add(row)
            db.flush()
            query_ids[query.source_plan_id] = row.id
        for result in results:
            signature = hashlib.sha256(
                ",".join(sorted(str(identifier) for identifier in result.candidate_ids)).encode()
            ).hexdigest()
            evaluation = IndexEvaluation(
                run_id=run.id,
                set_signature=signature,
                is_baseline=not result.candidate_ids,
                weighted_cost=result.weighted_cost,
                estimated_size_bytes=result.estimated_size_bytes,
                storage_complete=result.storage_complete,
                warnings=result.warnings,
            )
            db.add(evaluation)
            db.flush()
            db.add_all(
                EvaluationMember(
                    evaluation_id=evaluation.id,
                    candidate_id=index.candidate_id,
                    hypothetical_oid=index.hypothetical_oid,
                    hypothetical_name=index.hypothetical_name,
                    estimated_size_bytes=index.estimated_size_bytes,
                )
                for index in result.indexes
            )
            db.add_all(
                EvaluationPlan(
                    evaluation_id=evaluation.id,
                    query_id=query_ids[query.source_plan_id],
                    total_cost=query.plan.root.total_cost,
                    raw_explain=query.raw_explain,
                )
                for query in result.queries
            )
        identifier = run.id
    return get_run(engine, identifier)


def get_run(engine, identifier):
    with Session(engine) as db:
        run = db.get(EvaluationRun, identifier)
        if run is None:
            raise DomainError("not_found", "Hypothetical evaluation was not found.", 404)
        queries = list(
            db.scalars(
                select(EvaluationQuery)
                .where(EvaluationQuery.run_id == identifier)
                .order_by(EvaluationQuery.source_plan_id)
            )
        )
        by_id = {
            row.id: EvaluationQueryView(
                source_plan_id=row.source_plan_id,
                frequency=row.frequency,
                analysis=SQLAnalysis.model_validate(row.analysis),
            )
            for row in queries
        }
        evaluations = list(
            db.scalars(
                select(IndexEvaluation)
                .where(IndexEvaluation.run_id == identifier)
                .order_by(IndexEvaluation.is_baseline.desc(), IndexEvaluation.set_signature)
            )
        )
        ids = [row.id for row in evaluations]
        members = list(
            db.scalars(select(EvaluationMember).where(EvaluationMember.evaluation_id.in_(ids)))
        )
        plans = list(
            db.scalars(select(EvaluationPlan).where(EvaluationPlan.evaluation_id.in_(ids)))
        )
        baseline_row = next((row for row in evaluations if row.is_baseline), None)
        old_costs = {
            row.query_id: row.total_cost
            for row in plans
            if baseline_row and row.evaluation_id == baseline_row.id
        }
        results = []
        for evaluation in evaluations:
            indexes = [
                IndexEstimate(
                    candidate_id=row.candidate_id,
                    hypothetical_oid=row.hypothetical_oid,
                    hypothetical_name=row.hypothetical_name,
                    estimated_size_bytes=row.estimated_size_bytes,
                )
                for row in members
                if row.evaluation_id == evaluation.id
            ]
            indexes.sort(key=lambda row: str(row.candidate_id))
            names = {index.hypothetical_name: index.candidate_id for index in indexes}
            estimates = []
            for row in plans:
                if row.evaluation_id != evaluation.id:
                    continue
                query = by_id[row.query_id]
                document = explain_plan(parse_explain(row.raw_explain), query.analysis.tables)
                cost = document.root.total_cost
                previous = old_costs.get(row.query_id)
                used = sorted(
                    {
                        names[node.index_name]
                        for _, node in walk_plan(document.root)
                        if node.index_name in names
                    },
                    key=str,
                )
                estimates.append(
                    QueryEstimate(
                        source_plan_id=query.source_plan_id,
                        frequency=query.frequency,
                        plan=document,
                        raw_explain=row.raw_explain,
                        used_candidate_ids=used,
                        baseline_cost=previous,
                        estimated_improvement_pct=cost_reduction(previous, cost),
                        regression=cost > previous
                        if cost is not None and previous is not None
                        else None,
                    )
                )
            estimates.sort(key=lambda query: str(query.source_plan_id))
            base_cost = baseline_row.weighted_cost if baseline_row else None
            results.append(
                SetEstimate(
                    candidate_ids=[row.candidate_id for row in indexes],
                    indexes=indexes,
                    queries=estimates,
                    weighted_cost=evaluation.weighted_cost,
                    baseline_weighted_cost=base_cost,
                    estimated_improvement_pct=cost_reduction(base_cost, evaluation.weighted_cost),
                    estimated_size_bytes=evaluation.estimated_size_bytes,
                    storage_complete=evaluation.storage_complete,
                    warnings=evaluation.warnings,
                )
            )
        baseline = next((row for row in results if not row.candidate_ids), None)
        return EvaluationRunView(
            id=run.id,
            batch_id=run.batch_id,
            created_at=run.created_at,
            status=run.status,
            capability=run.capability,
            requested_sets=run.requested_sets,
            context=run.context,
            queries=list(by_id.values()),
            baseline=baseline,
            trials=[row for row in results if row.candidate_ids],
            warnings=run.warnings,
            error_code=run.error_code,
            cleanup_confirmed=run.cleanup_confirmed,
        )


def list_runs(engine, *, batch_id=None, limit=50, offset=0):
    with Session(engine) as db:
        statement = select(EvaluationRun)
        if batch_id:
            statement = statement.where(EvaluationRun.batch_id == batch_id)
        rows = db.scalars(
            statement.order_by(EvaluationRun.created_at.desc(), EvaluationRun.id)
            .offset(offset)
            .limit(limit)
        )
        return [EvaluationSummary.model_validate(row, from_attributes=True) for row in rows]
