import uuid

import pytest
from indexpilot.errors import DomainError
from indexpilot.evaluation.cache import RunCache
from indexpilot.evaluation.context import SourceQuery, replanning_query
from indexpilot.evaluation.costs import cost_reduction, weighted_cost
from indexpilot.evaluation.models import EvaluationRequest, SetEstimate
from indexpilot.sql.models import SQLAnalysis
from indexpilot.sql.validation import nodes, validate_sql
from pglast import ast, parse_sql
from pydantic import ValidationError


@pytest.mark.parametrize(
    "baseline,candidate,expected",
    [
        (100, 50, 50),
        (10, 20, -100),
        (10, 0, 100),
        (0, 0, None),
        (0, 1, None),
        (None, 1, None),
        (1, None, None),
        (-1, 1, None),
        (1, -1, None),
        (float("nan"), 1, None),
        (1, float("inf"), None),
        (1e-300, 1e300, None),
    ],
)
def test_cost_reduction_is_safe_and_keeps_regressions(baseline, candidate, expected):
    assert cost_reduction(baseline, candidate) == expected


def test_frequency_weighted_cost_is_arithmetic_not_milliseconds():
    assert weighted_cost([(100, 50), (1, 1000)]) == 6000
    assert weighted_cost([(1, None)]) is None
    assert weighted_cost([(0, 100)]) is None
    assert weighted_cost([(1, float("nan"))]) is None
    assert weighted_cost([(1e9, 1e308)]) is None
    assert weighted_cost([(1, 1e308), (1, 1e308)]) is None


@pytest.mark.parametrize(
    "groups",
    [[], [[]], [[1, 1]], [[1, 2], [2, 1]], [[*range(1, 34)]], [[number] for number in range(65)]],
)
def test_request_sets_are_bounded_and_unique(groups):
    converted = [[str(uuid.UUID(int=number)) for number in group] for group in groups]
    with pytest.raises(ValidationError):
        EvaluationRequest(batch_id=uuid.uuid4(), candidate_sets=converted)


def test_default_request_selects_auto_policy():
    assert EvaluationRequest(batch_id=uuid.uuid4()).candidate_sets is None


def value():
    return SetEstimate(
        candidate_ids=[],
        indexes=[],
        queries=[],
        weighted_cost=10,
        estimated_size_bytes=0,
        storage_complete=True,
        warnings=[],
    )


def test_cache_normalizes_set_order_and_protects_saved_results():
    first, second = uuid.uuid4(), uuid.uuid4()
    cache = RunCache(max_sets=1)
    original = value()
    cache.put([first, second], original)
    original.weighted_cost = 999
    fetched = cache.get([second, first])
    assert fetched.weighted_cost == 10
    fetched.weighted_cost = -1
    assert cache.get([first, second]).weighted_cost == 10
    with pytest.raises(DomainError):
        cache.require_room([])


def test_internal_replanning_preserves_bound_literals_and_builtin_operators():
    raw = (
        "SELECT CAST('O''Reilly; $1' AS pg_catalog.text) "
        "OPERATOR(pg_catalog.=) CAST('x' AS pg_catalog.text)"
    )
    analysis = SQLAnalysis(
        canonical_sql=raw,
        relations=[],
        columns=[],
        predicates=[],
        order_by=[],
        tables=[],
        warnings=[],
    )
    prepared = replanning_query(SourceQuery(uuid.uuid4(), 3, analysis))
    tree = validate_sql(prepared.sql)
    literals = [node.val.sval for node in nodes(tree) if isinstance(node, ast.A_Const)]
    assert literals == ["O'Reilly; $1", "x"]
    assert prepared.frequency == 3
    assert not any(isinstance(node, ast.ParamRef) for node in nodes(tree))
    assert len(parse_sql(prepared.sql)) == 1
