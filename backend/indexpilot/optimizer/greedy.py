from indexpilot.errors import DomainError
from indexpilot.evaluation.costs import cost_reduction
from indexpilot.optimizer.models import CandidateOutcome, OptimizationResult, Trial
from indexpilot.optimizer.objective import query_changes, score_set


def optimize(evaluator, candidates, options):
    """Pure bounded orchestration; evaluator owns all database/planner operations."""
    candidates = tuple(candidate.model_copy(deep=True) for candidate in candidates)
    options = options.model_copy(deep=True)
    by_id = {candidate.id: candidate for candidate in candidates}
    if len(by_id) != len(candidates) or len(candidates) > 32:
        raise DomainError(
            "invalid_candidates", "Optimization requires at most 32 distinct candidates."
        )
    if options.write_weights.keys() - by_id.keys():
        raise DomainError("invalid_write_weights", "Write weights must reference batch candidates.")
    ordered = sorted(candidates, key=lambda candidate: (candidate.signature, str(candidate.id)))
    baseline = evaluator.evaluate(frozenset())
    baseline_score = score_set(baseline, frozenset(), options, baseline)
    if not baseline_score.feasible:
        raise DomainError("unknown_baseline", "A complete baseline cost/storage is required.", 409)
    selected = []
    selected_ids = frozenset()
    current = baseline_score
    current_estimate = baseline
    trials = []
    evaluations = 1
    stop = "no_candidates"
    while len(selected) < len(candidates):
        remaining = [candidate for candidate in ordered if candidate.id not in selected_ids]
        if len(selected) >= options.max_selected_indexes:
            stop = "index_limit"
            break
        # Reserve a final uncached verification. Never choose from an incomplete round.
        if evaluations + len(remaining) + 1 > options.max_evaluations:
            stop = "evaluation_limit"
            break
        eligible = []
        for candidate in remaining:
            ids = selected_ids | {candidate.id}
            estimate = evaluator.evaluate(ids)
            evaluations += 1
            score = score_set(estimate, ids, options, baseline)
            gain = current.objective - score.objective if score.objective is not None else None
            additional = (
                score.storage_bytes - current.storage_bytes
                if score.storage_bytes is not None
                else None
            )
            reason = score.reason
            ratio = None
            if reason is None:
                if gain <= 0:
                    reason = "nonpositive_net_gain"
                elif additional <= 0:
                    reason = "nonpositive_incremental_storage"
                else:
                    ratio = gain / additional
                    reason = "lower_marginal_score"
            trial = Trial(
                step=len(selected) + 1,
                added_candidate_id=candidate.id,
                candidate_ids=sorted(ids, key=str),
                score=score,
                marginal_net_gain=gain,
                additional_bytes=additional,
                gain_per_byte=ratio,
                reason=reason,
                query_changes=query_changes(estimate, baseline),
            )
            trials.append(trial)
            if ratio is not None:
                eligible.append((trial, candidate, estimate))
        if not eligible:
            stop = "no_feasible_gain"
            break
        winner, candidate, current_estimate = min(
            eligible,
            key=lambda pair: (
                -pair[0].gain_per_byte,
                -pair[0].marginal_net_gain,
                pair[1].signature,
                str(pair[1].id),
            ),
        )
        winner.chosen, winner.reason = True, "selected"
        selected.append(candidate.id)
        selected_ids = frozenset(selected)
        current = winner.score
        stop = "candidates_exhausted"
    final = evaluator.evaluate(selected_ids, refresh=True)
    evaluations += 1
    final_score = score_set(final, selected_ids, options, baseline)
    if not final_score.feasible or (selected and final_score.objective >= baseline_score.objective):
        raise DomainError(
            "final_verification_failed",
            "Fresh final plans failed budget, cost or regression checks; no selection was saved.",
            409,
        )
    if final_score != current or any(
        change.absolute_change != 0 for change in query_changes(final, current_estimate)
    ):
        raise DomainError(
            "evaluation_context_changed",
            "Final cost/storage estimates changed during search; retry.",
            409,
        )
    warnings = [
        "Planner costs and HypoPG bytes are estimates; execution performance is unmeasured.",
        "Greedy search can miss complementary indexes and does not guarantee a global optimum.",
        "Write penalty is a user-configured heuristic, not measured write latency.",
    ]
    if stop in ("evaluation_limit", "index_limit"):
        warnings.append("Search stopped at a configured limit; unexplored alternatives remain.")
    last = {trial.added_candidate_id: trial.reason for trial in trials}
    return OptimizationResult(
        selected_candidate_ids=selected,
        baseline=baseline,
        final=final,
        baseline_score=baseline_score,
        final_score=final_score,
        estimated_read_improvement_pct=cost_reduction(
            baseline_score.read_cost, final_score.read_cost
        ),
        estimated_net_gain=baseline_score.objective - final_score.objective,
        trials=trials,
        candidates=[
            CandidateOutcome(
                candidate_id=candidate.id,
                selected=candidate.id in selected_ids,
                reason="selected"
                if candidate.id in selected_ids
                else last.get(candidate.id, "not_evaluated"),
            )
            for candidate in ordered
        ],
        stop_reason=stop,
        evaluations=evaluations,
        search_complete=stop not in ("evaluation_limit", "index_limit"),
        warnings=warnings,
    )
