import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import psycopg
import pytest
from fastapi.testclient import TestClient
from indexpilot.benchmarks import dataset
from indexpilot.benchmarks.guard import LOCK_KEY, isolation, namespace, verify
from indexpilot.benchmarks.jobs import cancel, enqueue, get_job, list_measurements, samples
from indexpilot.benchmarks.measurements import statistics_ms
from indexpilot.benchmarks.models import BenchmarkRequest
from indexpilot.benchmarks.pgbench import ContainerClient
from indexpilot.benchmarks.runner import run_next, terminate_clients
from indexpilot.errors import DomainError
from indexpilot.local import connect_local
from indexpilot.main import create_app
from indexpilot.metadata.models import (
    BenchmarkJob,
    BenchmarkQuery,
    MonitoredDatabase,
)
from psycopg import sql
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.integration.test_hypopg_evaluation import batch
from tests.integration.test_hypopg_evaluation import evaluation_api as evaluation_api
from tests.integration.test_hypopg_evaluation import evaluation_schema as evaluation_schema
from tests.integration.test_optimizer import post
from tests.integration.test_recommendations import recommend

pytestmark = pytest.mark.integration


def source(api):
    candidate = batch(
        api,
        "public",
        query={"sql": "SELECT id,status FROM public.orders WHERE user_id=101", "frequency": 100},
    )
    optimized = post(api, candidate["id"])
    assert optimized.status_code == 201, optimized.text
    return recommend(api, optimized.json()).json()


def queued(api, **changes):
    recommendation = source(api)
    request = BenchmarkRequest.model_validate(
        dict(
            recommendation_id=recommendation["id"],
            confirm_disposable_benchmark=True,
            orders=1000,
            repetitions=1,
            transactions_per_client=5,
            read_warmup_per_client=0,
        )
        | changes
    )
    return enqueue(api[2], request)


def test_actual_three_arm_pgbench_and_durable_transaction_samples(evaluation_api):
    job = queued(evaluation_api, clients=2)
    name = "m9_kept_" + uuid.uuid4().hex[:12]
    with connect_local("bench", autocommit=True) as connection:
        before = dataset.fingerprint(connection, "public")
        connection.execute(
            sql.SQL("CREATE INDEX {} ON public.orders(user_id)").format(sql.Identifier(name))
        )
        try:
            assert run_next(evaluation_api[2], evaluation_api[1]) == job.id
            saved = get_job(evaluation_api[2], job.id)
            assert saved.status == "completed", saved
            assert saved.cleanup_confirmed and saved.error_code is None
            assert dataset.fingerprint(connection, "public") == before
            assert (
                connection.execute("SELECT to_regclass(%s)", ("public." + name,)).fetchone()[0]
                is not None
            )
            assert (
                connection.execute("SELECT to_regnamespace(%s)", (namespace(job.id),)).fetchone()[0]
                is None
            )
        finally:
            connection.execute(sql.SQL("DROP INDEX public.{}").format(sql.Identifier(name)))
    measurements = list_measurements(evaluation_api[2], job.id)
    assert len(measurements) == 15 and {row.arm for row in measurements} == {
        "baseline",
        "per_query",
        "indexpilot",
    }
    fingerprints = {}
    for row in measurements:
        rows = samples(evaluation_api[2], row.id)
        assert len(rows) == 10
        parsed = [
            (sample["client_id"], sample["sequence"], sample["latency_us"], sample["script_id"])
            for sample in rows
        ]
        assert statistics_ms(parsed)["p95_ms"] == row.metrics["p95_ms"]
        assert row.metrics["tps"] > 0 and row.metrics["samples"] == 10
        assert row.conditions["additional_index_bytes_after"] >= 0
        assert row.conditions["orders_after"] == (1010 if row.phase == "insert" else 1000)
        assert row.conditions["dataset"] == fingerprints.setdefault(
            row.phase, row.conditions["dataset"]
        )
    with TestClient(create_app(evaluation_api[1])) as fresh:
        assert fresh.get(f"/api/v1/benchmarks/{job.id}").json() == saved.model_dump(mode="json")
        assert len(fresh.get(f"/api/v1/benchmarks/{job.id}/measurements").json()) == 15
    assert saved.manifest["benchmark_estimates"]["policy"] == "per-query-singleton-on-benchmark-v1"


@pytest.mark.parametrize("role", ["meta", "demo", "analyzer"])
def test_live_non_benchmark_connections_are_refused(role):
    with connect_local(role) as connection:
        with pytest.raises(DomainError):
            verify(connection)


def test_marker_and_alias_monitored_identity_refusals(evaluation_api):
    job = queued(evaluation_api)
    with connect_local("bench", autocommit=True) as connection:
        connection.execute("COMMENT ON DATABASE indexpilot_bench IS 'wrong-marker'")
        try:
            with pytest.raises(DomainError):
                isolation(connection, evaluation_api[1])
        finally:
            connection.execute(
                "COMMENT ON DATABASE indexpilot_bench IS 'indexpilot:disposable-benchmark:v1'"
            )
    with Session(evaluation_api[2]) as db, db.begin():
        alias = MonitoredDatabase(
            target_key="m9_alias_" + uuid.uuid4().hex,
            host="localhost",
            port=55432,
            database_name="indexpilot_bench",
            role_name="indexpilot_bench_owner",
            credential_reference="test_only",
        )
        db.add(alias)
        db.flush()
        identifier = alias.id
    try:
        with pytest.raises(DomainError):
            run_next(evaluation_api[2], evaluation_api[1])
        assert get_job(evaluation_api[2], job.id).status == "queued"
    finally:
        with Session(evaluation_api[2]) as db, db.begin():
            db.delete(db.get(MonitoredDatabase, identifier))
        cancel(evaluation_api[2], job.id)


def test_queue_confirmation_validation_and_cancel(evaluation_api):
    recommendation = source(evaluation_api)
    client = evaluation_api[0]
    for value in [False, 1, "true", None]:
        response = client.post(
            "/api/v1/benchmarks",
            json={"recommendation_id": recommendation["id"], "confirm_disposable_benchmark": value},
        )
        assert response.status_code == 422
    response = client.post(
        "/api/v1/benchmarks",
        json={
            "recommendation_id": recommendation["id"],
            "confirm_disposable_benchmark": True,
            "dsn": "forbidden",
        },
    )
    assert response.status_code == 422
    job = queued(evaluation_api)
    cancelled = cancel(evaluation_api[2], job.id)
    assert cancelled.status == "cancelled" and cancelled.cleanup_confirmed
    assert run_next(evaluation_api[2], evaluation_api[1]) is None


def test_running_pgbench_cancellation_removes_only_own_state(evaluation_api):
    job = queued(evaluation_api, transactions_per_client=10000)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_next, evaluation_api[2], evaluation_api[1])
        deadline = time.monotonic() + 30
        try:
            with connect_local("bench", autocommit=True) as connection:
                while time.monotonic() < deadline:
                    if connection.execute(
                        "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE application_name=%s)",
                        ("indexpilot-bench-" + job.id.hex,),
                    ).fetchone()[0]:
                        break
                    if future.done():
                        raise AssertionError("Benchmark ended before running cancellation probe")
                    time.sleep(0.05)
                else:
                    raise AssertionError("No running pgbench client observed")
            cancel(evaluation_api[2], job.id)
        finally:
            cancel(evaluation_api[2], job.id)
        assert future.result(timeout=90) == job.id
    saved = get_job(evaluation_api[2], job.id)
    assert saved.status == "cancelled" and saved.cleanup_confirmed
    with connect_local("bench") as connection:
        assert (
            connection.execute("SELECT to_regnamespace(%s)", (namespace(job.id),)).fetchone()[0]
            is None
        )


def test_interrupted_worker_is_recovered_before_next_claim(evaluation_api):
    job = queued(evaluation_api)
    with connect_local("bench", autocommit=True) as connection:
        expected = isolation(connection, evaluation_api[1])
        dataset.prepare(connection, job.id, expected, BenchmarkRequest.model_validate(job.request))
    with Session(evaluation_api[2]) as db, db.begin():
        row = db.get(BenchmarkJob, job.id)
        row.status = "running"
        row.started_at = datetime.now(UTC)
    assert run_next(evaluation_api[2], evaluation_api[1]) is None
    recovered = get_job(evaluation_api[2], job.id)
    assert (
        recovered.status == "failed"
        and recovered.error_code == "worker_interrupted"
        and recovered.cleanup_confirmed
    )


def test_other_worker_or_generator_locks_refuse_overlap(evaluation_api):
    queued(evaluation_api)
    with evaluation_api[2].connect() as coordinator:
        coordinator.execute(select(func.pg_advisory_lock(918273648)))
        try:
            with pytest.raises(DomainError, match="Another benchmark worker"):
                run_next(evaluation_api[2], evaluation_api[1])
        finally:
            coordinator.execute(select(func.pg_advisory_unlock(918273648)))
    with connect_local("bench", autocommit=True) as connection:
        connection.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            with pytest.raises(DomainError, match="target is busy"):
                run_next(evaluation_api[2], evaluation_api[1])
        finally:
            connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))


def test_cleanup_refuses_unknown_external_dependencies(evaluation_api):
    job = queued(evaluation_api)
    with connect_local("bench", autocommit=True) as connection:
        expected = isolation(connection, evaluation_api[1])
        dataset.prepare(connection, job.id, expected, BenchmarkRequest.model_validate(job.request))
        view = "m9_external_" + uuid.uuid4().hex[:12]
        connection.execute(
            sql.SQL("CREATE VIEW public.{} AS SELECT * FROM {}.orders").format(
                sql.Identifier(view), sql.Identifier(namespace(job.id))
            )
        )
        try:
            with pytest.raises(psycopg.errors.DependentObjectsStillExist):
                dataset.clean(connection, job.id, expected)
            assert (
                connection.execute("SELECT to_regnamespace(%s)", (namespace(job.id),)).fetchone()[0]
                is not None
            )
        finally:
            connection.execute(sql.SQL("DROP VIEW public.{}").format(sql.Identifier(view)))
            dataset.clean(connection, job.id, expected)
    cancel(evaluation_api[2], job.id)


def test_cooperative_job_timeout_cleans_real_pgbench_state(evaluation_api):
    job = queued(evaluation_api, orders=100000, transactions_per_client=10000, timeout_seconds=10)
    assert run_next(evaluation_api[2], evaluation_api[1]) == job.id
    saved = get_job(evaluation_api[2], job.id)
    assert (
        saved.status == "failed"
        and saved.error_code == "benchmark_timeout"
        and saved.cleanup_confirmed
    )


def test_bounded_queue_never_starts_unconfirmed_or_overflow_jobs(evaluation_api):
    recommendation = source(evaluation_api)
    body = BenchmarkRequest(
        recommendation_id=recommendation["id"], confirm_disposable_benchmark=True
    )
    jobs = [enqueue(evaluation_api[2], body) for _ in range(8)]
    with pytest.raises(DomainError, match="queue is full"):
        enqueue(evaluation_api[2], body)
    for job in jobs:
        assert cancel(evaluation_api[2], job.id).status == "cancelled"


def test_container_statement_timeout_is_enforced(evaluation_api):
    job = queued(evaluation_api)
    client = ContainerClient(job.id, lambda: None)
    with connect_local("bench", autocommit=True) as connection:
        expected = isolation(connection, evaluation_api[1])
        dataset.prepare(connection, job.id, expected, BenchmarkRequest.model_validate(job.request))
        client.setup()
        try:
            client.verify_nonce(namespace(job.id))
            with pytest.raises(DomainError, match="operation failed"):
                client.execute(
                    [("BEGIN;\nSELECT pg_catalog.pg_sleep(6);\nCOMMIT;\n", 1)],
                    clients=1,
                    transactions=5,
                    seed=42,
                    label="timeout_probe",
                )
        finally:
            terminate_clients(connection, client.application)
            dataset.clean(connection, job.id, expected)
            client.cleanup()
    cancel(evaluation_api[2], job.id)


def test_source_collation_mismatch_cannot_be_silently_reinterpreted(evaluation_api):
    job = queued(evaluation_api)
    with Session(evaluation_api[2]) as db, db.begin():
        row = db.scalar(select(BenchmarkQuery).where(BenchmarkQuery.job_id == job.id))
        import copy

        context = copy.deepcopy(row.analysis)
        column = next(item for item in context["tables"][0]["columns"] if item["name"] == "status")
        column.update(collation_oid=950, collation_schema="pg_catalog", collation_name="C")
        row.analysis = context
    assert run_next(evaluation_api[2], evaluation_api[1]) == job.id
    saved = get_job(evaluation_api[2], job.id)
    assert (
        saved.status == "failed"
        and saved.error_code == "benchmark_schema_mismatch"
        and saved.cleanup_confirmed
    )
    assert list_measurements(evaluation_api[2], job.id) == []


def test_actual_nonce_mismatch_and_pgbench_statement_failure(evaluation_api):
    job = queued(evaluation_api)
    client = ContainerClient(job.id, lambda: None)
    with connect_local("bench", autocommit=True) as connection:
        expected = isolation(connection, evaluation_api[1])
        dataset.prepare(connection, job.id, expected, BenchmarkRequest.model_validate(job.request))
        client.setup()
        try:
            connection.execute(
                sql.SQL("UPDATE {}.ip_guard SET token=%s").format(
                    sql.Identifier(namespace(job.id))
                ),
                (uuid.uuid4(),),
            )
            with pytest.raises(DomainError, match="same database"):
                client.verify_nonce(namespace(job.id))
            with pytest.raises(DomainError, match="operation failed"):
                client.execute(
                    [("BEGIN;\nSELECT 1/0;\nCOMMIT;\n", 1)],
                    clients=1,
                    transactions=5,
                    seed=42,
                    label="intentional_failure",
                )
        finally:
            terminate_clients(connection, client.application)
            dataset.clean(connection, job.id, expected)
            client.cleanup()
    cancel(evaluation_api[2], job.id)
