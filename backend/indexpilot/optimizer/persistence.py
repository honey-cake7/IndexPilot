import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from indexpilot.errors import DomainError
from indexpilot.evaluation.persistence import get_run, save_run
from indexpilot.metadata.models import (
    IndexEvaluation,
    OptimizationCandidate,
    OptimizationRun,
    OptimizationTrial,
)
from indexpilot.optimizer.models import OptimizationResult, OptimizationRunView, OptimizationSummary
from indexpilot.optimizer.objective import query_changes


def set_signature(ids):
    return hashlib.sha256(
        ",".join(sorted(str(identifier) for identifier in ids)).encode()
    ).hexdigest()


def save_optimization(engine, *, result, options, evidence):
    # Sessions bound to this Connection join its single outer transaction.
    with engine.begin() as connection:
        evaluation = save_run(connection, **evidence)
        with Session(connection) as db, db.begin():
            sets = {
                row.set_signature: row.id
                for row in db.scalars(
                    select(IndexEvaluation).where(IndexEvaluation.run_id == evaluation.id)
                )
            }
            run = OptimizationRun(
                evaluation_run_id=evaluation.id,
                final_evaluation_id=sets[set_signature(result.selected_candidate_ids)],
                options=options.model_dump(mode="json"),
                summary=result.model_dump(
                    mode="json",
                    exclude={"selected_candidate_ids", "baseline", "final", "trials", "candidates"},
                ),
            )
            db.add(run)
            db.flush()
            positions = {
                identifier: number
                for number, identifier in enumerate(result.selected_candidate_ids, 1)
            }
            db.add_all(
                OptimizationCandidate(
                    run_id=run.id,
                    candidate_id=outcome.candidate_id,
                    selected=outcome.selected,
                    selection_order=positions.get(outcome.candidate_id),
                    reason=outcome.reason,
                )
                for outcome in result.candidates
            )
            db.add_all(
                OptimizationTrial(
                    run_id=run.id,
                    evaluation_id=sets[set_signature(trial.candidate_ids)],
                    added_candidate_id=trial.added_candidate_id,
                    step=trial.step,
                    chosen=trial.chosen,
                    reason=trial.reason,
                    metrics=trial.model_dump(
                        mode="json",
                        exclude={
                            "candidate_ids",
                            "added_candidate_id",
                            "step",
                            "chosen",
                            "reason",
                            "query_changes",
                        },
                    ),
                )
                for trial in result.trials
            )
            identifier = run.id
    return get_optimization(engine, identifier)


def get_optimization(engine, identifier):
    with Session(engine) as db:
        run = db.get(OptimizationRun, identifier)
        if run is None:
            raise DomainError("not_found", "Optimization was not found.", 404)
        evidence = get_run(db.connection(), run.evaluation_run_id)
        sets = {
            set_signature(result.candidate_ids): result
            for result in [evidence.baseline, *evidence.trials]
        }
        final_key = db.get(IndexEvaluation, run.final_evaluation_id).set_signature
        outcomes = list(
            db.scalars(select(OptimizationCandidate).where(OptimizationCandidate.run_id == run.id))
        )
        selected = [
            row.candidate_id
            for row in sorted(
                [row for row in outcomes if row.selected], key=lambda row: row.selection_order
            )
        ]
        rows = db.execute(
            select(OptimizationTrial, IndexEvaluation.set_signature)
            .join(IndexEvaluation, IndexEvaluation.id == OptimizationTrial.evaluation_id)
            .where(OptimizationTrial.run_id == run.id)
            .order_by(OptimizationTrial.step, OptimizationTrial.id)
        ).all()
        trials = [
            dict(
                **row.metrics,
                step=row.step,
                added_candidate_id=row.added_candidate_id,
                candidate_ids=sets[key].candidate_ids,
                chosen=row.chosen,
                reason=row.reason,
                query_changes=query_changes(sets[key], evidence.baseline),
            )
            for row, key in rows
        ]
        # Stable history ordering; selected order is stored separately in normalized rows.
        trials.sort(key=lambda trial: (trial["step"], trial["added_candidate_id"].hex))
        result = OptimizationResult(
            **run.summary,
            selected_candidate_ids=selected,
            baseline=evidence.baseline,
            final=sets[final_key],
            trials=trials,
            candidates=[
                dict(candidate_id=row.candidate_id, selected=row.selected, reason=row.reason)
                for row in sorted(outcomes, key=lambda row: str(row.candidate_id))
            ],
        )
        return OptimizationRunView(
            id=run.id,
            evaluation_run_id=run.evaluation_run_id,
            batch_id=evidence.batch_id,
            created_at=run.created_at,
            options=run.options,
            result=result,
            cleanup_confirmed=evidence.cleanup_confirmed,
            context=evidence.context,
        )


def list_optimizations(engine, *, limit=50, offset=0):
    with Session(engine) as db:
        rows = db.scalars(
            select(OptimizationRun)
            .order_by(OptimizationRun.created_at.desc(), OptimizationRun.id)
            .limit(limit)
            .offset(offset)
        )
        return [OptimizationSummary.model_validate(row, from_attributes=True) for row in rows]
