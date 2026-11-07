from pathlib import Path

import pytest
from indexpilot.errors import DomainError
from indexpilot.sql.validation import nodes, split_workload, validate_sql
from indexpilot.workloads.manual import prepare_query
from indexpilot.workloads.models import ManualWorkloadInput, Parameter, QueryInput
from pglast import ast
from pydantic import ValidationError


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "CREATE INDEX ON orders(user_id)",
        "EXPLAIN SELECT 1",
        "SELECT 1; SELECT 2",
        "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x",
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "SELECT * INTO copied FROM orders",
        "SELECT * FROM orders FOR UPDATE",
        "SELECT pg_sleep(1)",
        "SELECT nextval('x')",
        "SELECT set_config('x','y',false)",
        "SELECT public.sum(id) FROM orders",
        "SELECT count(*) OVER () FROM orders",
        "SELECT * FROM generate_series(1,5)",
        "SELECT * FROM (SELECT 1) x",
        "SELECT 1 UNION SELECT 2",
        "VALUES (1)",
        "SELECT * FROM private.orders",
        "SELECT 1::public.evil",
        "SELECT 1::int[]",
        "SELECT 1 OPERATOR(public.=) 1",
        "SELECT (SELECT 1)",
        "SELECT $0",
        "SELECT $101",
        "SELECT * FROM orders NATURAL JOIN users",
        "SELECT 1\x00; DELETE FROM orders",
        "select from",
        "-- comment only",
        "SELECT '\ud800'",
    ],
)
def test_rejects_unsupported_or_unsafe_sql(sql):
    with pytest.raises(DomainError):
        validate_sql(sql)


def test_all_documented_sample_queries_are_admitted():
    for statement in split_workload(Path("sample/workload.sql").read_text()):
        assert isinstance(validate_sql(statement), ast.SelectStmt)


def test_normalization_preserves_scenarios_and_collapses_literals():
    first = prepare_query(QueryInput(sql="SELECT id FROM orders WHERE user_id=101", frequency=100))
    second = prepare_query(QueryInput(sql="SELECT id FROM orders WHERE user_id=202", frequency=5))
    assert first.fingerprint == second.fingerprint
    assert first.normalized == second.normalized
    assert first.representative != second.representative
    assert first.original.frequency == 100 and second.original.frequency == 5


def test_ast_parameter_binding_keeps_malicious_text_a_literal():
    value = "O'Reilly; DELETE FROM orders; -- $1"
    query = prepare_query(
        QueryInput(
            sql="SELECT id FROM users WHERE email=$1 OR email=$1",
            parameters={1: Parameter(type="text", value=value)},
        )
    )
    bound = validate_sql(query.representative)
    constants = [node.val.sval for node in nodes(bound) if isinstance(node, ast.A_Const)]
    assert constants == [value, value]
    assert query.missing_parameters == []


def test_missing_unused_and_noncontiguous_parameters():
    query = prepare_query(QueryInput(sql="SELECT id FROM orders WHERE user_id=$2"))
    assert query.representative is None and query.missing_parameters == [2]
    with pytest.raises(DomainError, match="unused"):
        prepare_query(QueryInput(sql="SELECT 1", parameters={1: Parameter(type="int8", value=1)}))
    bound = prepare_query(
        QueryInput(sql="SELECT $2", parameters={2: Parameter(type="text", value=None)})
    )
    assert "NULL" in bound.representative


def test_split_handles_comments_unicode_and_semicolons_inside_literals():
    statements = split_workload("-- note\nSELECT 'नमस्ते;世界'; /* ; */ SELECT 2;")
    assert len(statements) == 2
    for statement in statements:
        validate_sql(statement)


@pytest.mark.parametrize("frequency", [0, -1, float("inf"), float("nan"), 1_000_000_001])
def test_rejects_invalid_frequency(frequency):
    with pytest.raises(ValidationError):
        QueryInput(sql="SELECT 1", frequency=frequency)


def test_bounds_file_and_query_count():
    with pytest.raises(DomainError):
        split_workload("SELECT 1;" * 101)
    with pytest.raises(DomainError):
        split_workload("SELECT '" + "a" * 65536 + "'")
    with pytest.raises(DomainError):
        split_workload("")
    with pytest.raises(ValidationError):
        ManualWorkloadInput(queries=[])


def test_fingerprints_include_explicit_schema_scope():
    schemas = ("public", "another", "third")

    def prepare(sql):
        return prepare_query(QueryInput(sql=sql), allowed_schemas=schemas).fingerprint

    assert prepare("SELECT id FROM orders") == prepare("SELECT id FROM public.orders")
    assert prepare("SELECT id FROM another.orders") != prepare("SELECT id FROM third.orders")


@pytest.mark.parametrize("value", ["bad\x00value", "\ud800"])
def test_parameter_values_reject_unrepresentable_postgresql_text(value):
    with pytest.raises(ValidationError):
        Parameter(type="text", value=value)
