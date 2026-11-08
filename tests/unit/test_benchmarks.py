import uuid

import pytest
from indexpilot.benchmarks.dataset import rebind_sql
from indexpilot.benchmarks.guard import namespace, require_namespace, same_database
from indexpilot.benchmarks.measurements import compare, parse_log, parse_summary, statistics_ms
from indexpilot.benchmarks.models import BenchmarkRequest
from indexpilot.benchmarks.pgbench import read_script, write_script
from indexpilot.config import Settings
from indexpilot.errors import DomainError
from indexpilot.sql.models import SQLAnalysis
from pydantic import ValidationError


def request(**changes):
    return BenchmarkRequest.model_validate(
        dict(recommendation_id=str(uuid.uuid4()), confirm_disposable_benchmark=True) | changes
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"confirm_disposable_benchmark": False},
        {"confirm_disposable_benchmark": 1},
        {"orders": 999},
        {"orders": 100001},
        {"orders": True},
        {"repetitions": 0},
        {"clients": 5},
        {"transactions_per_client": 4},
        {"read_warmup_per_client": -1},
        {"timeout_seconds": 601},
        {"regression_threshold_pct": float("nan")},
        {"regression_threshold_pct": -1},
        {"target": "demo"},
        {"sql": "DROP INDEX bad"},
        {"dsn": "postgresql://forbidden"},
    ],
)
def test_benchmark_bounds_and_explicit_boolean_confirmation(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_confirmation_is_required():
    with pytest.raises(ValidationError):
        BenchmarkRequest(recommendation_id=uuid.uuid4())


@pytest.mark.parametrize("value", [0, 5001])
def test_statistics_capture_remains_bounded(value):
    with pytest.raises(ValidationError):
        Settings(statistics_collection_limit=value)


def test_statistics_default_unchanged_and_larger_history_is_explicit():
    assert Settings().statistics_collection_limit == 1000
    assert Settings(statistics_collection_limit=5000).statistics_collection_limit == 5000


def test_actual_log_shape_and_percentiles_from_individual_samples():
    rows = parse_log(
        "0 1 1000 0 1700000000 123\n0 2 3000 0 1700000000 999\n",
        clients=1,
        transactions=2,
        scripts=1,
    )
    stats = statistics_ms(rows)
    assert stats == dict(samples=2, mean_ms=2, median_ms=2, p95_ms=3)
    assert statistics_ms([])["p95_ms"] is None


@pytest.mark.parametrize(
    "raw",
    [
        "0 1 failed 0 10 0",
        "0 1 skipped 0 10 0",
        "0 1 1 2 10 0",
        "1 1 1 0 10 0",
        "0 0 1 0 10 0",
        "0 1 -1 0 10 0",
        "0 1 1.0 0 10 0",
        "0 1 1 0 10 1000000",
        "0 1 1 0 10",
        "",
        "0 1 1 0 10 0\n0 1 2 0 10 1",
    ],
)
def test_incomplete_failed_duplicate_or_malformed_log_is_not_success(raw):
    with pytest.raises(DomainError):
        parse_log(raw, clients=1, transactions=1, scripts=1)


def test_parse_complete_pgbench_stdout():
    stdout = (
        "number of transactions actually processed: 10/10\n"
        "number of failed transactions: 0 (0%)\n"
        "tps = 1234.56 (without initial connection time)\n"
    )
    assert parse_summary(stdout, 10) == 1234.56
    for text in [
        stdout.replace("10/10", "9/10"),
        stdout.replace("transactions: 0", "transactions: 1"),
        stdout.replace("1234.56", "0"),
        "latency average = 1 ms",
    ]:
        with pytest.raises(DomainError):
            parse_summary(text, 10)


def test_regression_threshold_and_zero_measured_baseline():
    rows = [
        dict(phase="read_q0", arm=arm, metrics={"mean_ms": value})
        for arm, value in [("baseline", 100), ("per_query", 110), ("indexpilot", 120)]
    ]
    result = compare(rows, 10)
    assert not result[0]["regression"] and result[1]["regression"]
    assert result[1]["measured_improvement_pct"] == pytest.approx(-20)
    for row in rows:
        row["metrics"]["mean_ms"] = 0
    assert all(
        row["regression"] is None and row["measured_improvement_pct"] is None
        for row in compare(rows, 10)
    )


@pytest.mark.parametrize(
    "name", ["public", "indexpilot_demo", "ipb_bad", "ipb_" + "1" * 31, "ipb_" + "1" * 32 + ";DROP"]
)
def test_namespace_cannot_escape_job_owned_scope(name):
    with pytest.raises(DomainError):
        require_namespace(name)


def test_alias_identity_uses_server_and_database_not_connection_hostname():
    left = dict(
        address="127.0.0.1",
        port=5432,
        server_start="instant",
        database_oid=42,
        hostname="localhost",
    )
    right = dict(left, hostname="127.0.0.1")
    assert same_database(left, right)
    assert not same_database(left, dict(right, database_oid=43))


@pytest.mark.parametrize(
    "value", ["SELECT 'line\n\\shell bad'", "SELECT 'back\\slash'", "SELECT * FROM private.orders"]
)
def test_pgbench_language_escape_or_non_sample_schema_is_rejected(value):
    context = SQLAnalysis(
        canonical_sql=value,
        relations=[],
        columns=[],
        predicates=[],
        order_by=[],
        tables=[],
        warnings=[],
    )
    with pytest.raises(DomainError):
        rebind_sql(context, namespace(uuid.uuid4()))


def test_read_and_write_scripts_are_explicit_transactions():
    assert read_script("SELECT 1") == "BEGIN READ ONLY;\nSELECT 1;\nCOMMIT;\n"
    for value in ["SELECT 'a\nb'", "SELECT '\\shell bad'"]:
        with pytest.raises(DomainError):
            read_script(value)
    for operation in ["insert", "update", "delete"]:
        script = write_script(namespace(uuid.uuid4()), operation, 1000)
        assert script.startswith("BEGIN;") and script.endswith("COMMIT;\n")
    with pytest.raises(ValueError):
        write_script(namespace(uuid.uuid4()), "arbitrary", 1000)
