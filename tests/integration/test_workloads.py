import uuid

import pytest
from fastapi.testclient import TestClient
from indexpilot.config import Settings
from indexpilot.errors import DomainError
from indexpilot.local import ROLES, connect_local
from indexpilot.main import create_app
from indexpilot.metadata.models import (
    QueryPattern,
    QueryScenario,
    QueryStatistic,
    Workload,
    WorkloadSnapshot,
)
from indexpilot.metadata.session import metadata_engine
from indexpilot.workloads.collector import collect_snapshot
from indexpilot.workloads.deltas import snapshot_delta
from indexpilot.workloads.models import SnapshotView
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture
def api():
    prefix = f"m3-test-{uuid.uuid4()}"
    # Capture the pinned server's full bounded 5,000-entry history, not an assumed empty cluster.
    with TestClient(create_app(Settings(statistics_collection_limit=5000))) as client:
        yield client, prefix
    engine = metadata_engine(Settings())
    try:
        with Session(engine) as session, session.begin():
            ids = select(Workload.id).where(Workload.name.like(prefix + "%"))
            patterns = select(QueryPattern.id).where(QueryPattern.workload_id.in_(ids))
            snapshots = select(WorkloadSnapshot.id).where(WorkloadSnapshot.workload_id.in_(ids))
            session.execute(delete(QueryStatistic).where(QueryStatistic.snapshot_id.in_(snapshots)))
            session.execute(delete(QueryScenario).where(QueryScenario.pattern_id.in_(patterns)))
            session.execute(delete(WorkloadSnapshot).where(WorkloadSnapshot.workload_id.in_(ids)))
            session.execute(delete(QueryPattern).where(QueryPattern.workload_id.in_(ids)))
            session.execute(delete(Workload).where(Workload.id.in_(ids)))
    finally:
        engine.dispose()


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setitem(ROLES, "test_admin", ("indexpilot_demo", "postgres", "admin_password"))
    with connect_local("test_admin", autocommit=True) as connection:
        yield connection


def test_manual_persistence_grouping_and_frequency(api):
    client, name = api
    response = client.post(
        "/api/v1/workloads/manual",
        json={
            "name": name,
            "queries": [
                {"sql": "SELECT id FROM orders WHERE user_id=101", "frequency": 100},
                {"sql": "SELECT id FROM orders WHERE user_id=202", "frequency": 5},
            ],
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert len(data["patterns"]) == 1
    assert sorted(row["frequency"] for row in data["patterns"][0]["scenarios"]) == [5, 100]
    assert data == client.get(f"/api/v1/workloads/{data['id']}").json()
    # A separate app/metadata connection sees the saved records too.
    with TestClient(create_app()) as second_client:
        assert second_client.get(f"/api/v1/workloads/{data['id']}").json() == data
    assert any(item["id"] == data["id"] for item in client.get("/api/v1/workloads").json())


def test_unbound_parameters_and_multiple_representatives(api):
    client, name = api
    data = client.post(
        "/api/v1/workloads/manual",
        json={
            "name": name,
            "queries": [
                {"sql": "SELECT id FROM orders WHERE user_id=$1", "frequency": 50},
            ],
        },
    ).json()
    pattern = data["patterns"][0]
    assert pattern["scenarios"][0]["representative_sql"] is None
    assert pattern["scenarios"][0]["missing_parameters"] == [1]
    for value, frequency in ((101, 40), (202, 10)):
        response = client.post(
            f"/api/v1/query-patterns/{pattern['id']}/scenarios",
            json={
                "parameters": {"1": {"type": "int8", "value": value}},
                "frequency": frequency,
            },
        )
        assert response.status_code == 201, response.text
        assert str(value) in response.json()["representative_sql"]
        assert response.json()["validation"] == "syntax_only"
    invalid = client.post(
        f"/api/v1/query-patterns/{pattern['id']}/scenarios", json={"parameters": {}}
    )
    assert invalid.status_code == 422


def test_sql_paste_and_real_multipart_upload(api):
    client, name = api
    pasted = client.post(
        "/api/v1/workloads/sql",
        json={
            "name": name,
            "sql": "SELECT id FROM users; SELECT id FROM products;",
            "frequency": 7,
        },
    )
    assert pasted.status_code == 201 and pasted.json()["pattern_total"] == 2
    uploaded = client.post(
        "/api/v1/workloads/upload",
        data={"name": name, "frequency": "3"},
        files={"file": ("workload.sql", b"\xef\xbb\xbfSELECT 'a;b'; SELECT 3;", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert sum(len(pattern["scenarios"]) for pattern in uploaded.json()["patterns"]) == 2
    assert all(s["frequency"] == 3 for p in uploaded.json()["patterns"] for s in p["scenarios"])


@pytest.mark.parametrize(
    "filename,content",
    [
        ("bad.txt", b"SELECT 1"),
        ("bad.sql", b"\xff"),
        ("empty.sql", b""),
        ("big.sql", b" " * 65537),
        ("bad.sql", b"DELETE FROM orders"),
    ],
)
def test_invalid_uploads(api, filename, content):
    client, name = api
    response = client.post(
        "/api/v1/workloads/upload", data={"name": name}, files={"file": (filename, content)}
    )
    assert response.status_code == 422


def test_invalid_batch_is_atomic_and_input_is_never_executed(api, caplog):
    client, name = api
    response = client.post(
        "/api/v1/workloads/manual",
        json={
            "name": name,
            "queries": [
                {"sql": "SELECT 'private-literal-marker'"},
                {"sql": "DELETE FROM orders"},
            ],
        },
    )
    assert response.status_code == 422
    assert "private-literal-marker" not in response.text + caplog.text
    engine = metadata_engine(Settings())
    try:
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count()).select_from(Workload).where(Workload.name == name)
                )
                == 0
            )
    finally:
        engine.dispose()
    # Syntactic ingestion succeeds without accessing even a nonexistent target table.
    response = client.post(
        "/api/v1/workloads/manual",
        json={
            "name": name,
            "queries": [
                {"sql": "SELECT id FROM public.m3_table_that_does_not_exist"},
            ],
        },
    )
    assert response.status_code == 201


def test_live_snapshots_deltas_and_representative_parameters(api):
    client, name = api
    workload = client.post("/api/v1/workloads/collected", json={"name": name}).json()
    with connect_local("analyzer", autocommit=True) as connection:
        probe = "SELECT sum(id), max(user_id), min(total) FROM public.orders WHERE user_id=779"
        connection.execute(probe).fetchall()
        first_response = client.post(f"/api/v1/workloads/{workload['id']}/snapshots")
        assert first_response.status_code == 201, first_response.text
        first = first_response.json()
        for _ in range(3):
            connection.execute(probe).fetchall()
        second = client.post(f"/api/v1/workloads/{workload['id']}/snapshots").json()
    matching = [
        row for row in second["entries"] if "sum(id), max(user_id), min(total)" in row["query"]
    ]
    assert len(matching) == 1
    identity = matching[0]["identity"]
    delta = client.get(f"/api/v1/snapshots/{second['id']}/delta").json()
    row = next(row for row in delta["entries"] if row["identity"] == identity)
    assert row["usable"] and row["calls"] == 3
    assert row["mean_exec_ms"] == pytest.approx(row["total_exec_ms"] / 3)
    assert client.get(f"/api/v1/snapshots/{second['id']}").json() == second
    assert len(client.get(f"/api/v1/workloads/{workload['id']}/snapshots").json()) == 2
    initial_delta = client.get(f"/api/v1/snapshots/{first['id']}/delta").json()
    assert all(not row["usable"] for row in initial_delta["entries"])
    patterns = client.get(f"/api/v1/workloads/{workload['id']}").json()["patterns"]
    pattern = next(pattern for pattern in patterns if pattern["identity"] == identity)
    scenario = client.post(
        f"/api/v1/query-patterns/{pattern['id']}/scenarios",
        json={
            "parameters": {"1": {"type": "int8", "value": 779}},
            "frequency": 3,
        },
    )
    assert scenario.status_code == 201, scenario.text


def test_real_per_entry_reset_is_detected(admin):
    with connect_local("analyzer", autocommit=True) as connection:
        probe = "SELECT min(id), min(user_id), max(total) FROM public.orders WHERE user_id=778"
        connection.execute(probe).fetchall()
        before = collect_snapshot(connection, limit=5000)
        row = next(item for item in before.entries if "min(user_id)" in item.query)
        admin.execute(
            "SELECT pg_stat_statements_reset(%s::oid, %s::oid, %s::bigint)",
            (
                row.userid,
                row.dbid,
                row.queryid,
            ),
        )
        connection.execute(probe).fetchall()
        after = collect_snapshot(connection, limit=5000)
    workload_id = uuid.uuid4()
    previous = SnapshotView(id=uuid.uuid4(), workload_id=workload_id, **before.model_dump())
    current = SnapshotView(id=uuid.uuid4(), workload_id=workload_id, **after.model_dump())
    result = next(
        item for item in snapshot_delta(previous, current).entries if item.identity == row.identity
    )
    assert not result.usable and result.reason in ("entry_reset", "new_entry_without_baseline")


def test_inaccessible_statistics_returns_api_error(api, admin):
    client, name = api
    workload = client.post("/api/v1/workloads/collected", json={"name": name}).json()
    assert admin.execute(
        "SELECT has_table_privilege('indexpilot_analyzer', 'public.pg_stat_statements','SELECT')"
    ).fetchone()[0]
    admin.execute("REVOKE SELECT ON public.pg_stat_statements FROM PUBLIC")
    try:
        response = client.post(f"/api/v1/workloads/{workload['id']}/snapshots")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "statistics_unavailable"
    finally:
        admin.execute("GRANT SELECT ON public.pg_stat_statements TO PUBLIC")


def test_missing_extension_is_a_real_capability_failure(monkeypatch):
    monkeypatch.setitem(ROLES, "test_no_extension", ("postgres", "postgres", "admin_password"))
    with connect_local("test_no_extension") as connection:
        with pytest.raises(DomainError) as error:
            collect_snapshot(connection)
        assert error.value.code == "statistics_unavailable"


def test_truncation_is_explicit():
    with connect_local("analyzer") as connection:
        data = collect_snapshot(connection, limit=1)
    assert data.truncated and data.warnings


def test_wrong_source_and_unknown_resource(api):
    client, name = api
    manual = client.post(
        "/api/v1/workloads/manual",
        json={
            "name": name,
            "queries": [{"sql": "SELECT 1"}],
        },
    ).json()
    assert client.post(f"/api/v1/workloads/{manual['id']}/snapshots").status_code == 422
    assert client.get(f"/api/v1/workloads/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/v1/workloads/not-a-uuid").status_code == 422


def test_pattern_pagination_and_cross_workload_deltas(api):
    client, name = api
    data = client.post(
        "/api/v1/workloads/sql",
        json={
            "name": name,
            "sql": "SELECT id FROM users; SELECT id FROM products;",
        },
    ).json()
    first = client.get(f"/api/v1/workloads/{data['id']}?limit=1").json()
    second = client.get(f"/api/v1/workloads/{data['id']}?limit=1&offset=1").json()
    assert first["pattern_total"] == second["pattern_total"] == 2
    assert first["patterns"][0]["id"] != second["patterns"][0]["id"]
    ids = []
    for _ in range(2):
        workload = client.post("/api/v1/workloads/collected", json={"name": name}).json()
        ids.append(client.post(f"/api/v1/workloads/{workload['id']}/snapshots").json()["id"])
    response = client.get(f"/api/v1/snapshots/{ids[1]}/delta?previous_id={ids[0]}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "different_workloads"


def test_minmax_only_reset_keeps_cumulative_interval_usable(admin):
    with connect_local("analyzer", autocommit=True) as connection:
        probe = "SELECT max(id), max(user_id), max(total) FROM public.orders WHERE user_id=777"
        connection.execute(probe).fetchall()
        before = collect_snapshot(connection, limit=5000)
        row = next(
            item for item in before.entries if "max(id), max(user_id), max(total)" in item.query
        )
        admin.execute(
            "SELECT pg_stat_statements_reset(%s::oid, %s::oid, %s::bigint, true)",
            (
                row.userid,
                row.dbid,
                row.queryid,
            ),
        )
        connection.execute(probe).fetchall()
        after = collect_snapshot(connection, limit=5000)
    workload_id = uuid.uuid4()
    previous = SnapshotView(id=uuid.uuid4(), workload_id=workload_id, **before.model_dump())
    current = SnapshotView(id=uuid.uuid4(), workload_id=workload_id, **after.model_dump())
    result = next(
        item for item in snapshot_delta(previous, current).entries if item.identity == row.identity
    )
    assert result.usable and result.calls == 1
