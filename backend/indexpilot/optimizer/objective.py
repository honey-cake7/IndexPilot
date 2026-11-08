import math

from indexpilot.errors import DomainError
from indexpilot.evaluation.costs import cost_reduction, weighted_cost
from indexpilot.optimizer.models import ObjectiveScore, QueryChange


def query_changes(estimate, baseline):
    old = {query.source_plan_id: query for query in baseline.queries}
    current = {query.source_plan_id: query for query in estimate.queries}
    if (
        len(old) != len(baseline.queries)
        or len(current) != len(estimate.queries)
        or old.keys() != current.keys()
    ):
        raise DomainError("invalid_evaluation", "Trial query membership changed.", 409)
    changes = []
    for identifier in sorted(old, key=str):
        previous, query = old[identifier], current[identifier]
        if query.frequency != previous.frequency:
            raise DomainError("invalid_evaluation", "Trial query frequencies changed.", 409)
        before, after = previous.plan.root.total_cost, query.plan.root.total_cost
        known = before is not None and after is not None
        changes.append(
            QueryChange(
                source_plan_id=identifier,
                frequency=query.frequency,
                baseline_cost=before,
                cost=after,
                absolute_change=after - before if known else None,
                estimated_improvement_pct=cost_reduction(before, after),
                regression=after > before if known else None,
            )
        )
    return changes


def score_set(estimate, expected_ids, options, baseline):
    expected = set(expected_ids)
    if len(estimate.candidate_ids) != len(expected) or set(estimate.candidate_ids) != expected:
        raise DomainError("invalid_evaluation", "Trial candidate membership changed.", 409)
    sizes = {index.candidate_id: index.estimated_size_bytes for index in estimate.indexes}
    if len(sizes) != len(estimate.indexes) or sizes.keys() != expected:
        raise DomainError("invalid_evaluation", "Trial index membership changed.", 409)
    read = weighted_cost(
        (query.frequency, query.plan.root.total_cost) for query in estimate.queries
    )
    if not estimate.queries:
        read = None
    known = estimate.storage_complete and all(
        isinstance(size, int) and not isinstance(size, bool) and 0 < size <= 2**63 - 1
        for size in sizes.values()
    )
    storage = sum(sizes.values()) if known else None
    if storage is not None and storage > 2**63 - 1:
        storage = None
    if storage is not None and estimate.estimated_size_bytes != storage:
        raise DomainError("invalid_evaluation", "Trial total bytes differ from its members.", 409)
    penalty = 0.0
    if options.write_penalty_cost_per_mib:
        penalty = (
            math.fsum(
                options.write_penalty_cost_per_mib
                * options.write_weights.get(identifier, 1)
                * (size / 1048576)
                for identifier, size in sizes.items()
            )
            if storage is not None
            else None
        )
    objective = read + penalty if read is not None and penalty is not None else None
    if objective is not None and not math.isfinite(objective):
        objective = None
    reason = None
    if read is None or objective is None:
        reason = "unknown_cost"
    elif storage is None:
        reason = "unknown_storage"
    elif storage > options.storage_budget_bytes:
        reason = "storage_budget"
    changes = query_changes(estimate, baseline)
    if reason is None and options.max_query_regression_pct is not None:
        for change in changes:
            if change.regression:
                if change.baseline_cost == 0:
                    reason = "undefined_regression_ratio"
                elif change.cost > change.baseline_cost + change.baseline_cost * (
                    options.max_query_regression_pct / 100
                ):
                    reason = "query_regression_limit"
                if reason:
                    break
    return ObjectiveScore(
        read_cost=read,
        storage_bytes=storage,
        write_penalty=penalty,
        objective=objective,
        feasible=reason is None,
        reason=reason,
    )
