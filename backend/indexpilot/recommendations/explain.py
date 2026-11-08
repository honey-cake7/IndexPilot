import math

from indexpilot.errors import DomainError
from indexpilot.evaluation.costs import cost_reduction, weighted_cost
from indexpilot.plans.parser import walk_plan
from indexpilot.recommendations.models import (
    IndexExplanation,
    PlanComparison,
    QueryExplanation,
    RecommendationSummaryData,
)

VERSION = "recommendation-explanations-v1"
WRITE_OVERHEAD = (
    "Additional B-Tree indexes can add storage and maintenance for inserts, deletes and updates "
    "to indexed columns. Write latency, WAL and maintenance overhead have not been measured."
)
SQL_WARNINGS = [
    "SQL is a historical proposal for human review; no command has been executed.",
    "Check current schema, existing indexes, name conflicts, disk space and locking before use.",
    "Hypothetical cost/size estimates do not establish runtime benefit or final physical size.",
]


def invalid_source():
    return DomainError(
        "invalid_recommendation_source",
        "Saved optimization evidence is inconsistent; rerun it.",
        409,
    )


def statistics_warnings(analysis):
    columns = {
        (table.oid, column.name): column for table in analysis.tables for column in table.columns
    }
    warnings = [
        *analysis.warnings,
        *(warning for table in analysis.tables for warning in table.warnings),
    ]
    if any(
        columns.get((usage.column.relation_oid, usage.column.name)) is None
        or columns[(usage.column.relation_oid, usage.column.name)].statistics is None
        for usage in analysis.columns
    ):
        warnings.append(
            "At least one referenced column has no visible statistics; estimates may be uncertain."
        )
    if any(
        table.last_analyze is None and table.last_autoanalyze is None for table in analysis.tables
    ):
        warnings.append("An ANALYZE timestamp is unavailable for at least one referenced table.")
    return warnings


def query_explanation(before, after, analysis, baseline_workload_cost):
    old, new = before.plan.root.total_cost, after.plan.root.total_cost
    if old is None or new is None or before.frequency != after.frequency:
        raise invalid_source()
    old_weighted, new_weighted = (
        weighted_cost([(before.frequency, old)]),
        weighted_cost([(after.frequency, new)]),
    )
    if old_weighted is None or new_weighted is None:
        raise invalid_source()
    reduction = old_weighted - new_weighted
    contribution = (
        (reduction / baseline_workload_cost) * 100 if baseline_workload_cost > 0 else None
    )
    if contribution is not None and not math.isfinite(contribution):
        contribution = None
    old_types = sorted({node.node_type for _, node in walk_plan(before.plan.root)})
    new_types = sorted({node.node_type for _, node in walk_plan(after.plan.root)})
    observations = [
        f"Estimated root cost changed from {old:g} to {new:g} planner units.",
        f"Final plan references {len(after.used_candidate_ids)} selected hypothetical index(es).",
    ]
    if old_types != new_types:
        observations.append(
            "Observed plan node types changed; this is an estimated plan comparison."
        )
    warnings = statistics_warnings(analysis)
    if new > old:
        warnings.append(
            "This query regresses in estimated cost even if the total workload improves."
        )
    if old == 0:
        warnings.append("Baseline query cost is zero; relative improvement is undefined.")
    return QueryExplanation(
        baseline_cost=old,
        final_cost=new,
        estimated_cost_reduction=old - new,
        estimated_improvement_pct=cost_reduction(old, new),
        baseline_weighted_cost=old_weighted,
        final_weighted_cost=new_weighted,
        estimated_weighted_cost_reduction=reduction,
        contribution_to_baseline_pct=contribution,
        regression=new > old,
        warnings=list(dict.fromkeys(warnings)),
        comparison=PlanComparison(
            baseline_node_types=old_types,
            final_node_types=new_types,
            baseline_index_names=sorted(
                {node.index_name for _, node in walk_plan(before.plan.root) if node.index_name}
            ),
            final_used_candidate_ids=after.used_candidate_ids,
            observations=observations,
        ),
    )


def index_explanation(trial, previous_score, used):
    read_gain = previous_score.read_cost - trial.score.read_cost
    penalty = trial.score.write_penalty - previous_score.write_penalty
    if (
        not trial.chosen
        or trial.marginal_net_gain is None
        or trial.gain_per_byte is None
        or trial.marginal_net_gain <= 0
        or not math.isclose(
            read_gain - penalty, trial.marginal_net_gain, rel_tol=1e-9, abs_tol=1e-9
        )
    ):
        raise invalid_source()
    warnings = [
        "This is the gain when added to the preceding selected set, not an independent final gain.",
        "Final query improvement belongs to the whole set and cannot be assigned to every index.",
    ]
    if not used:
        warnings.append(
            "No final plan references this index; its selection-step evidence is retained."
        )
    return IndexExplanation(
        selection_reason=(
            f"Chosen at step {trial.step}: estimated objective decreased by "
            f"{trial.marginal_net_gain:g} weighted planner units, "
            f"at {trial.gain_per_byte:g} units per additional estimated byte."
        ),
        selection_step_read_cost_reduction=read_gain,
        selection_step_net_gain=trial.marginal_net_gain,
        selection_step_penalty_increase=penalty,
        gain_per_additional_byte=trial.gain_per_byte,
        write_overhead=WRITE_OVERHEAD,
        warnings=warnings,
    )


def summary(result, options):
    return RecommendationSummaryData(
        selected_count=len(result.selected_candidate_ids),
        storage_budget_bytes=options.storage_budget_bytes,
        estimated_size_bytes=result.final_score.storage_bytes,
        baseline_score=result.baseline_score,
        final_score=result.final_score,
        estimated_read_improvement_pct=result.estimated_read_improvement_pct,
        estimated_net_gain=result.estimated_net_gain,
        stop_reason=result.stop_reason,
        search_complete=result.search_complete,
        evaluations=result.evaluations,
        message=(
            f"Selected {len(result.selected_candidate_ids)} B-Tree index(es), estimated at "
            f"{result.final_score.storage_bytes} bytes within "
            f"a {options.storage_budget_bytes}-byte "
            f"estimated budget. Weighted planner cost: {result.baseline_score.read_cost:g} to "
            f"{result.final_score.read_cost:g}. Execution performance is unmeasured."
        ),
    )
