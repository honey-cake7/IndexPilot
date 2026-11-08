"""Explicit arithmetic fixtures test selection rules, never PostgreSQL effectiveness."""

import uuid

import pytest
from indexpilot.errors import DomainError
from indexpilot.evaluation.models import IndexEstimate, QueryEstimate, SetEstimate
from indexpilot.optimizer.greedy import optimize
from indexpilot.optimizer.models import OptimizationOptions, SearchCandidate
from indexpilot.plans.models import PlanDocument, PlanNode
from pydantic import ValidationError

A, B = uuid.UUID(int=1), uuid.UUID(int=2)
Q1, Q2 = uuid.UUID(int=101), uuid.UUID(int=102)


class ArithmeticEvaluator:
    def __init__(self, costs, sizes=None, frequencies=(1,), final=None):
        self.costs = {frozenset(key): value for key, value in costs.items()}
        self.sizes = sizes or {A: 100, B: 100}
        self.frequencies = frequencies
        self.final = final
        self.calls = []

    def evaluate(self, ids=frozenset(), *, refresh=False):
        ids = frozenset(ids)
        self.calls.append((ids, refresh))
        if refresh and self.final:
            return self.final(ids)
        values = self.costs[ids]
        indexes = [
            IndexEstimate(
                candidate_id=identifier,
                hypothetical_oid=number + 1,
                hypothetical_name=str(identifier),
                estimated_size_bytes=self.sizes[identifier],
            )
            for number, identifier in enumerate(sorted(ids))
        ]
        complete = all(index.estimated_size_bytes is not None for index in indexes)
        return SetEstimate(
            candidate_ids=sorted(ids),
            indexes=indexes,
            queries=[
                QueryEstimate(
                    source_plan_id=identifier,
                    frequency=frequency,
                    plan=PlanDocument(
                        root=PlanNode(node_type="Result", total_cost=cost),
                        node_count=1,
                        observations=[],
                        warnings=[],
                    ),
                    raw_explain=[],
                    used_candidate_ids=[],
                )
                for identifier, cost, frequency in zip(
                    (Q1, Q2), values, self.frequencies, strict=False
                )
            ],
            # Intentionally unusable summary: optimizer must calculate from roots/frequencies.
            weighted_cost=None,
            estimated_size_bytes=sum(index.estimated_size_bytes for index in indexes)
            if complete
            else None,
            storage_complete=complete,
            warnings=[],
        )


def run(evaluator, ids=(A, B), **options):
    return optimize(
        evaluator,
        [SearchCandidate(id=identifier, signature=str(identifier)) for identifier in ids],
        OptimizationOptions(
            storage_budget_bytes=options.pop("storage_budget_bytes", 200), **options
        ),
    )


@pytest.mark.parametrize("frequencies,selected", [((100, 1), A), ((1, 100), B)])
def test_frequencies_reverse_selection(frequencies, selected):
    evaluator = ArithmeticEvaluator(
        {(): [100, 100], (A,): [10, 100], (B,): [100, 10]}, frequencies=frequencies
    )
    result = run(evaluator, max_selected_indexes=1)
    assert result.selected_candidate_ids == [selected]
    assert result.baseline_score.read_cost == 10100
    assert result.final_verified and evaluator.calls[-1] == (frozenset({selected}), True)


def test_overlapping_gain_is_recomputed_against_the_selected_set():
    evaluator = ArithmeticEvaluator({(): [100], (A,): [60], (B,): [70], (A, B): [60]})
    result = run(evaluator)
    assert result.selected_candidate_ids == [A]
    combined = next(trial for trial in result.trials if len(trial.candidate_ids) == 2)
    assert combined.marginal_net_gain == 0 and combined.reason == "nonpositive_net_gain"
    assert result.estimated_read_improvement_pct == pytest.approx(40)


def test_complementary_pair_demonstrates_greedy_limitation():
    evaluator = ArithmeticEvaluator({(): [100], (A,): [100], (B,): [100], (A, B): [1]})
    result = run(evaluator)
    assert result.selected_candidate_ids == []
    assert result.stop_reason == "no_feasible_gain"
    assert evaluator.costs[frozenset({A, B})][0] < result.final_score.read_cost
    assert any("complementary" in warning for warning in result.warnings)


@pytest.mark.parametrize("budget,selected", [(100, [A]), (99, []), (0, [])])
def test_exact_storage_budget_and_empty_solution(budget, selected):
    result = run(
        ArithmeticEvaluator({(): [100], (A,): [50]}), ids=(A,), storage_budget_bytes=budget
    )
    assert result.selected_candidate_ids == selected
    assert result.final_score.storage_bytes <= budget


@pytest.mark.parametrize("size", [None, 0, -1])
def test_unknown_and_nonpositive_sizes_are_never_free(size):
    result = run(ArithmeticEvaluator({(): [100], (A,): [1]}, sizes={A: size}), ids=(A,))
    assert result.selected_candidate_ids == []
    assert result.trials[0].reason == "unknown_storage"


def test_unknown_trial_cost_is_not_zero():
    result = run(ArithmeticEvaluator({(): [100], (A,): [None]}), ids=(A,))
    assert result.selected_candidate_ids == []
    assert result.trials[0].reason == "unknown_cost"


def test_zero_baseline_is_valid_without_relative_percentage():
    result = run(ArithmeticEvaluator({(): [0], (A,): [0]}), ids=(A,))
    assert result.selected_candidate_ids == []
    assert result.estimated_read_improvement_pct is None and result.estimated_net_gain == 0


def test_missing_baseline_is_an_error():
    with pytest.raises(DomainError) as caught:
        run(ArithmeticEvaluator({(): [None]}), ids=())
    assert caught.value.code == "unknown_baseline"


def test_heuristic_penalty_changes_selection_without_changing_read_improvement_units():
    evaluator = ArithmeticEvaluator(
        {(): [100], (A,): [10], (B,): [30]}, sizes={A: 1048576, B: 1048576}
    )
    result = run(
        evaluator,
        storage_budget_bytes=1048576,
        max_selected_indexes=1,
        write_penalty_cost_per_mib=10,
        write_weights={A: 10, B: 1},
    )
    assert result.selected_candidate_ids == [B]
    assert result.final_score.write_penalty == 10
    assert result.final_score.objective == 40 and result.estimated_net_gain == 60
    assert result.estimated_read_improvement_pct == pytest.approx(70)


@pytest.mark.parametrize("limit,selected", [(9, []), (10, [A]), (None, [A])])
def test_regression_limit_is_relative_to_baseline_and_includes_boundary(limit, selected):
    result = run(
        ArithmeticEvaluator({(): [100, 100], (A,): [10, 110]}, frequencies=(1, 1)),
        ids=(A,),
        max_query_regression_pct=limit,
    )
    assert result.selected_candidate_ids == selected
    assert result.trials[0].query_changes[1].regression


def test_positive_regression_from_zero_is_not_assigned_a_ratio():
    result = run(
        ArithmeticEvaluator({(): [100, 0], (A,): [0, 1]}, frequencies=(1, 1)),
        ids=(A,),
        max_query_regression_pct=100,
    )
    assert result.selected_candidate_ids == []
    assert result.trials[0].reason == "undefined_regression_ratio"


def test_equal_ratio_tie_uses_absolute_gain_then_canonical_signature():
    evaluator = ArithmeticEvaluator({(): [100], (A,): [90], (B,): [80]}, sizes={A: 10, B: 20})
    assert run(evaluator, max_selected_indexes=1).selected_candidate_ids == [B]
    for ids in [(B, A), (A, B)]:
        equal = ArithmeticEvaluator({(): [100], (A,): [90], (B,): [90]})
        assert run(equal, ids=ids, max_selected_indexes=1).selected_candidate_ids == [A]


@pytest.mark.parametrize("limit,selected,calls", [(2, [], 2), (4, [A], 4)])
def test_evaluation_limit_reserves_final_verification_and_requires_complete_round(
    limit, selected, calls
):
    evaluator = ArithmeticEvaluator({(): [100], (A,): [10], (B,): [20]})
    result = run(evaluator, max_evaluations=limit)
    assert result.selected_candidate_ids == selected
    assert result.stop_reason == "evaluation_limit" and not result.search_complete
    assert result.evaluations == calls == len(evaluator.calls)
    assert evaluator.calls[-1][1]


def test_zero_selected_cap_and_no_candidates_still_verify_baseline():
    evaluator = ArithmeticEvaluator({(): [100]})
    result = run(evaluator, max_selected_indexes=0)
    assert result.stop_reason == "index_limit" and result.evaluations == 2
    empty = run(ArithmeticEvaluator({(): [100]}), ids=())
    assert empty.stop_reason == "no_candidates" and empty.selected_candidate_ids == []


@pytest.mark.parametrize("change", ["storage", "cost", "improved_cost"])
def test_fresh_final_drift_cannot_publish_a_selection(change):
    evaluator = ArithmeticEvaluator({(): [100], (A,): [50]})
    other = ArithmeticEvaluator(
        {(A,): [150 if change == "cost" else 40 if change == "improved_cost" else 50]},
        sizes={A: 999 if change == "storage" else 100},
    )
    evaluator.final = other.evaluate
    with pytest.raises(DomainError) as caught:
        run(evaluator, ids=(A,))
    assert caught.value.code in ("final_verification_failed", "evaluation_context_changed")


@pytest.mark.parametrize(
    "changes",
    [
        {"storage_budget_bytes": -1},
        {"storage_budget_bytes": 1.5},
        {"storage_budget_bytes": True},
        {"max_evaluations": 1},
        {"max_evaluations": 1025},
        {"max_selected_indexes": 33},
        {"write_penalty_cost_per_mib": -1},
        {"write_penalty_cost_per_mib": float("nan")},
        {"max_query_regression_pct": float("inf")},
        {"max_query_regression_pct": -1},
        {"write_weights": {A: float("nan")}},
        {"write_weights": {A: -1}},
    ],
)
def test_invalid_search_options(changes):
    with pytest.raises(ValidationError):
        OptimizationOptions.model_validate({"storage_budget_bytes": 100, **changes})


def test_unknown_write_weight_and_duplicate_candidates_are_rejected():
    with pytest.raises(DomainError, match="Write weights"):
        run(ArithmeticEvaluator({(): [100]}), ids=(), write_weights={A: 1})
    with pytest.raises(DomainError, match="distinct"):
        run(ArithmeticEvaluator({(): [100]}), ids=(A, A))


def test_combined_storage_is_checked_instead_of_adding_singleton_estimates():
    class ChangingSize(ArithmeticEvaluator):
        def evaluate(self, ids=frozenset(), *, refresh=False):
            result = super().evaluate(ids, refresh=refresh)
            if len(ids) == 2:
                for index in result.indexes:
                    index.estimated_size_bytes = 150
                result.estimated_size_bytes = 300
            return result

    result = run(ChangingSize({(): [100], (A,): [60], (B,): [70], (A, B): [10]}))
    assert result.selected_candidate_ids == [A]
    assert result.trials[-1].reason == "storage_budget"
    assert result.trials[-1].score.storage_bytes == 300


def test_multiple_selections_use_the_new_marginal_gain_and_positive_total_storage():
    result = run(ArithmeticEvaluator({(): [100], (A,): [70], (B,): [80], (A, B): [50]}))
    assert result.selected_candidate_ids == [A, B]
    assert [trial.marginal_net_gain for trial in result.trials if trial.chosen] == [30, 20]
    assert result.final_score.storage_bytes == 200 and result.stop_reason == "candidates_exhausted"


def test_failed_evaluation_aborts_instead_of_becoming_zero_cost():
    class Failing(ArithmeticEvaluator):
        def evaluate(self, ids=frozenset(), *, refresh=False):
            if ids:
                raise DomainError("statement_timeout", "Test timeout.", 504)
            return super().evaluate(ids, refresh=refresh)

    with pytest.raises(DomainError) as caught:
        run(Failing({(): [100]}), ids=(A,))
    assert caught.value.code == "statement_timeout"


@pytest.mark.parametrize("mutation", ["membership", "frequency", "bytes"])
def test_evaluator_context_or_member_total_mismatch_is_rejected(mutation):
    class Changed(ArithmeticEvaluator):
        def evaluate(self, ids=frozenset(), *, refresh=False):
            result = super().evaluate(ids, refresh=refresh)
            if ids:
                if mutation == "membership":
                    result.candidate_ids = []
                elif mutation == "frequency":
                    result.queries[0].frequency = 99
                else:
                    result.estimated_size_bytes = 1
            return result

    with pytest.raises(DomainError) as caught:
        run(Changed({(): [100], (A,): [1]}), ids=(A,))
    assert caught.value.code == "invalid_evaluation"


@pytest.mark.parametrize("frequency", [-1, float("inf"), float("nan")])
def test_invalid_baseline_frequency_is_not_accepted(frequency):
    with pytest.raises(DomainError) as caught:
        run(ArithmeticEvaluator({(): [100]}, frequencies=(frequency,)), ids=())
    assert caught.value.code in ("unknown_baseline", "invalid_evaluation")


def test_tie_break_uses_signature_before_uuid():
    evaluator = ArithmeticEvaluator({(): [100], (A,): [50], (B,): [50]})
    result = optimize(
        evaluator,
        [SearchCandidate(id=A, signature="z"), SearchCandidate(id=B, signature="a")],
        OptimizationOptions(storage_budget_bytes=100, max_selected_indexes=1),
    )
    assert result.selected_candidate_ids == [B]


@pytest.mark.parametrize("combined_member_bytes", [50, 25])
def test_nonpositive_additional_bytes_never_divides_by_zero(combined_member_bytes):
    class ShrinkingEstimate(ArithmeticEvaluator):
        def evaluate(self, ids=frozenset(), *, refresh=False):
            result = super().evaluate(ids, refresh=refresh)
            if len(ids) == 2:
                for index in result.indexes:
                    index.estimated_size_bytes = combined_member_bytes
                result.estimated_size_bytes = 2 * combined_member_bytes
            return result

    result = run(ShrinkingEstimate({(): [100], (A,): [60], (B,): [70], (A, B): [10]}))
    assert result.selected_candidate_ids == [A]
    assert result.trials[-1].reason == "nonpositive_incremental_storage"
