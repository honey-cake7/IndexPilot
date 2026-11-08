"""Synthetic arithmetic/quoting checks; real evidence is tested separately in PostgreSQL."""

import uuid
from types import SimpleNamespace

import pytest
from indexpilot.candidates.sql import candidate_key, definition
from indexpilot.errors import DomainError
from indexpilot.optimizer.models import ObjectiveScore, Trial
from indexpilot.recommendations.explain import (
    index_explanation,
    query_explanation,
    statistics_warnings,
)
from indexpilot.recommendations.models import RecommendationRequest
from indexpilot.recommendations.service import validated_definition
from indexpilot.sql.models import ColumnUsage, SQLAnalysis
from pglast import ast, parse_sql
from pydantic import ValidationError

from tests.unit.test_candidates import CLASSES, column, table
from tests.unit.test_optimizer import A, ArithmeticEvaluator


def analysis():
    return SQLAnalysis(
        canonical_sql="SELECT 1",
        relations=[],
        columns=[],
        predicates=[],
        order_by=[],
        tables=[],
        warnings=[],
    )


@pytest.mark.parametrize(
    "before,after,frequency,baseline,percentage,contribution",
    [
        (100, 50, 10, 1000, 50, 50),
        (100, 110, 2, 1000, -10, -2),
        (0, 0, 1, 0, None, None),
        (100, 100, 1, 100, 0, 0),
        (1, 0, 100, 1000, 100, 10),
    ],
)
def test_query_contribution_uses_frequency_and_whole_workload_baseline(
    before, after, frequency, baseline, percentage, contribution
):
    estimates = ArithmeticEvaluator({(): [before], (A,): [after]}, frequencies=(frequency,))
    old, new = estimates.evaluate().queries[0], estimates.evaluate({A}).queries[0]
    result = query_explanation(old, new, analysis(), baseline)
    assert result.estimated_weighted_cost_reduction == frequency * (before - after)
    assert (
        result.estimated_improvement_pct == pytest.approx(percentage)
        if percentage is not None
        else result.estimated_improvement_pct is None
    )
    assert (
        result.contribution_to_baseline_pct == pytest.approx(contribution)
        if contribution is not None
        else result.contribution_to_baseline_pct is None
    )
    assert result.regression is (after > before)
    if after > before:
        assert any("regresses" in warning for warning in result.warnings)


def trial():
    return Trial(
        step=1,
        added_candidate_id=A,
        candidate_ids=[A],
        chosen=True,
        reason="selected",
        score=ObjectiveScore(
            read_cost=70, storage_bytes=100, write_penalty=5, objective=75, feasible=True
        ),
        marginal_net_gain=25,
        additional_bytes=100,
        gain_per_byte=0.25,
        query_changes=[],
    )


def test_selection_step_read_gain_and_penalty_are_not_final_attribution():
    previous = ObjectiveScore(
        read_cost=100, storage_bytes=0, write_penalty=0, objective=100, feasible=True
    )
    result = index_explanation(trial(), previous, {uuid.uuid4()})
    assert result.selection_step_read_cost_reduction == 30
    assert result.selection_step_net_gain == 25 and result.selection_step_penalty_increase == 5
    assert result.attribution == "selection_step_marginal"
    assert any("whole set" in warning for warning in result.warnings)
    assert "not been measured" in result.write_overhead


@pytest.mark.parametrize(
    "changes", [{"chosen": False}, {"marginal_net_gain": 30}, {"gain_per_byte": None}]
)
def test_inconsistent_selection_cannot_generate_an_explanation(changes):
    previous = ObjectiveScore(
        read_cost=100, storage_bytes=0, write_penalty=0, objective=100, feasible=True
    )
    with pytest.raises(DomainError):
        index_explanation(trial().model_copy(update=changes), previous, set())


def test_unused_index_is_explicitly_uncertain():
    previous = ObjectiveScore(
        read_cost=100, storage_bytes=0, write_penalty=0, objective=100, feasible=True
    )
    assert any(
        "No final plan" in warning
        for warning in index_explanation(trial(), previous, set()).warnings
    )


def test_missing_statistics_and_analyze_time_remain_uncertain():
    target = table()
    target.columns[0].statistics = None
    context = analysis()
    context.tables = [target]
    context.columns = [ColumnUsage(column=column(target, "user_id"), contexts=["where"])]
    warnings = statistics_warnings(context)
    assert any("no visible statistics" in warning for warning in warnings)
    assert any("timestamp is unavailable" in warning for warning in warnings)


@pytest.mark.parametrize("changes", ["ddl", "signature", "column"])
def test_saved_definition_must_match_quoted_structure(changes):
    target = table()
    candidate = definition(target, [candidate_key(target.columns[0], CLASSES[20])])
    data = candidate.model_dump()
    if changes == "ddl":
        data["ddl"] += "; SELECT 1"
    elif changes == "signature":
        data["signature"] = "x" * 64
    else:
        data["keys"][0]["column"] = "missing"
    with pytest.raises(DomainError):
        validated_definition(
            SimpleNamespace(definition=data, signature=candidate.signature), {target.oid: target}
        )


def test_quoted_definition_compiles_one_index_statement_without_execution():
    target = table(schema='odd"; schema', name='orders"; --', names=('user"id;',))
    candidate = definition(target, [candidate_key(target.columns[0], CLASSES[20])])
    rebuilt = validated_definition(
        SimpleNamespace(definition=candidate.model_dump(), signature=candidate.signature),
        {target.oid: target},
    )
    nodes = parse_sql(rebuilt.ddl + ";")
    assert len(nodes) == 1 and isinstance(nodes[0].stmt, ast.IndexStmt)
    assert nodes[0].stmt.relation.relname == target.name
    assert nodes[0].stmt.relation.schemaname == target.schema_name
    assert nodes[0].stmt.indexParams[0].name == target.columns[0].name


@pytest.mark.parametrize(
    "data", [{}, {"optimization_id": "bad"}, {"optimization_id": str(A), "sql": "CREATE INDEX bad"}]
)
def test_recommendation_request_never_accepts_arbitrary_commands(data):
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(data)
