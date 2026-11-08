import uuid

import pytest
from fastapi.testclient import TestClient
from indexpilot.config import Settings
from indexpilot.local import connect_local
from indexpilot.main import create_app
from indexpilot.metadata.models import (
    CandidateBatch,
    CandidateBatchSource,
    IndexCandidate,
    IndexCandidateEvidence,
    PlanAnalysis,
)
from indexpilot.metadata.session import metadata_engine
from psycopg import sql
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def candidate_schema():
    schema = "m5_" + uuid.uuid4().hex[:12]
    with connect_local("demo", autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        connection.execute(
            sql.SQL("SET search_path TO {},pg_catalog").format(sql.Identifier(schema))
        )
        connection.execute(
            """
          CREATE TABLE orders(id bigint PRIMARY KEY,user_id bigint,created_at timestamptz,
            state text,category varchar(40),region bigint);
          INSERT INTO orders SELECT n,n%100,TIMESTAMPTZ '2025-01-01 UTC'+n*INTERVAL '1 day',
            CASE WHEN n%2=0 THEN 'paid' ELSE 'pending' END,'cat-'||n%10,n%8
            FROM generate_series(1,1000) n;
          CREATE INDEX existing_user ON orders(user_id);
          CREATE INDEX partial_region ON orders(region) WHERE state='paid';
          CREATE INDEX expression_state ON orders((pg_catalog.lower(state)));
          CREATE INDEX covering_date ON orders(created_at) INCLUDE(state);
          CREATE INDEX pattern_state ON orders(state text_pattern_ops);
          CREATE TABLE "Odd;Table"("User;ID" bigint,"Date" timestamptz);
          CREATE TABLE freshness(id bigint);
          ANALYZE orders;
        """,
            prepare=False,
        )
        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO indexpilot_analyzer").format(
                sql.Identifier(schema)
            )
        )
        connection.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO indexpilot_analyzer").format(
                sql.Identifier(schema)
            )
        )
    yield schema
    with connect_local("demo", autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def candidates_api(candidate_schema):
    settings = Settings(analysis_schemas=("public", candidate_schema))
    plan_ids, batch_ids = [], []
    with TestClient(create_app(settings)) as client:
        yield client, settings, plan_ids, batch_ids
    engine = metadata_engine(settings)
    try:
        with Session(engine) as session, session.begin():
            candidate_ids = select(IndexCandidate.id).where(IndexCandidate.batch_id.in_(batch_ids))
            session.execute(
                delete(IndexCandidateEvidence).where(
                    IndexCandidateEvidence.candidate_id.in_(candidate_ids)
                )
            )
            session.execute(delete(IndexCandidate).where(IndexCandidate.batch_id.in_(batch_ids)))
            session.execute(
                delete(CandidateBatchSource).where(CandidateBatchSource.batch_id.in_(batch_ids))
            )
            session.execute(delete(CandidateBatch).where(CandidateBatch.id.in_(batch_ids)))
            session.execute(delete(PlanAnalysis).where(PlanAnalysis.id.in_(plan_ids)))
    finally:
        engine.dispose()


def analyze(api, query):
    client, _, plan_ids, _ = api
    response = client.post("/api/v1/plans", json={"sql": query})
    assert response.status_code == 201, response.text
    plan_ids.append(uuid.UUID(response.json()["id"]))
    return response.json()["id"]


def generate(api, plan_ids, **settings):
    client, _, _, batch_ids = api
    response = client.post("/api/v1/candidates", json={"plan_ids": plan_ids, **settings})
    if response.status_code == 201:
        batch_ids.append(uuid.UUID(response.json()["id"]))
    return response


def key_names(candidate):
    return [key["column"] for key in candidate["definition"]["keys"]]


def test_real_candidate_batch_and_hypopg_ddl_validation(candidates_api, candidate_schema):
    query = (
        f"SELECT id FROM {candidate_schema}.orders WHERE user_id=5 "
        "AND created_at >= TIMESTAMPTZ '2025-02-01 UTC' ORDER BY created_at DESC"
    )
    plan_id = analyze(candidates_api, query)
    response = generate(candidates_api, [plan_id])
    assert response.status_code == 201, response.text
    data = response.json()
    assert any(
        key_names(row) == ["user_id", "created_at"] and row["definition"]["keys"][1]["descending"]
        for row in data["proposed"]
    )
    assert any(
        row["rejection_reason"] == "exact_duplicate" and key_names(row) == ["user_id"]
        for row in data["rejected"]
    )
    with connect_local("analyzer", autocommit=True) as connection:
        real_before = connection.execute(
            "SELECT count(*) FROM pg_index WHERE indrelid=%s::regclass",
            (f"{candidate_schema}.orders",),
        ).fetchone()[0]
        try:
            for candidate in data["proposed"]:
                assert candidate["evaluation_status"] == "not_evaluated"
                assert candidate["estimated_size_bytes"] is None
                assert candidate["estimated_improvement_pct"] is None
                oid = connection.execute(
                    "SELECT indexrelid FROM public.hypopg_create_index(%s)",
                    (candidate["definition"]["ddl"],),
                ).fetchone()[0]
                assert oid > 0
                connection.execute("SELECT public.hypopg_reset()")
        finally:
            connection.execute("SELECT public.hypopg_reset()")
        assert (
            connection.execute(
                "SELECT count(*) FROM pg_index WHERE indrelid=%s::regclass",
                (f"{candidate_schema}.orders",),
            ).fetchone()[0]
            == real_before
        )
    client, _, _, _ = candidates_api
    assert client.get(f"/api/v1/candidates/{data['id']}").json() == data
    with TestClient(create_app(candidates_api[1])) as second:
        assert second.get(f"/api/v1/candidates/{data['id']}").json() == data
    assert any(row["id"] == data["id"] for row in client.get("/api/v1/candidates?limit=100").json())


def test_partial_covering_expression_and_opclass_differences_remain(
    candidates_api, candidate_schema
):
    plan_id = analyze(
        candidates_api,
        f"SELECT id FROM {candidate_schema}.orders WHERE region=2 AND state='paid' "
        "AND created_at >= TIMESTAMPTZ '2025-01-01 UTC'",
    )
    data = generate(candidates_api, [plan_id]).json()
    assert any(key_names(row) == ["region"] for row in data["proposed"])
    state = next(row for row in data["proposed"] if key_names(row) == ["state"])
    assert state["definition"]["keys"][0]["operator_class"]["name"] == "text_ops"
    assert any(key_names(row) == ["created_at"] and row["warnings"] for row in data["proposed"])
    with connect_local("analyzer") as connection:
        try:
            assert (
                connection.execute(
                    "SELECT indexrelid FROM public.hypopg_create_index(%s)",
                    (state["definition"]["ddl"],),
                ).fetchone()[0]
                > 0
            )
        finally:
            connection.execute("SELECT public.hypopg_reset()")


def test_primary_key_coverage_and_varchar_default_opclass(candidates_api, candidate_schema):
    plan_id = analyze(
        candidates_api, f"SELECT id FROM {candidate_schema}.orders WHERE id=1 AND category='cat-1'"
    )
    data = generate(candidates_api, [plan_id]).json()
    assert any(
        key_names(row) == ["id"] and row["rejection_reason"] == "covered_by_unique_index"
        for row in data["rejected"]
    )
    varchar = next(row for row in data["proposed"] if key_names(row) == ["category"])
    assert varchar["definition"]["keys"][0]["operator_class"]["name"] == "text_ops"
    with connect_local("analyzer") as connection:
        try:
            assert (
                connection.execute(
                    "SELECT indexrelid FROM public.hypopg_create_index(%s)",
                    (varchar["definition"]["ddl"],),
                ).fetchone()[0]
                > 0
            )
        finally:
            connection.execute("SELECT public.hypopg_reset()")


def test_new_index_after_source_plan_is_seen_during_generation(candidates_api, candidate_schema):
    plan_id = analyze(
        candidates_api,
        f"SELECT id FROM {candidate_schema}.orders WHERE user_id=5 "
        "AND created_at >= TIMESTAMPTZ '2025-02-01 UTC' ORDER BY created_at DESC",
    )
    with connect_local("demo", autocommit=True) as owner:
        owner.execute(
            sql.SQL(
                "CREATE INDEX later_exact ON {}.orders"
                "(user_id ASC NULLS LAST,created_at DESC NULLS FIRST)"
            ).format(sql.Identifier(candidate_schema))
        )
        try:
            data = generate(candidates_api, [plan_id]).json()
            assert any(
                key_names(row) == ["user_id", "created_at"]
                and row["definition"]["keys"][1]["descending"]
                and row["rejection_reason"] == "exact_duplicate"
                and "later_exact" in row["existing_indexes"]
                for row in data["rejected"]
            )
        finally:
            owner.execute(
                sql.SQL("DROP INDEX {}.later_exact").format(sql.Identifier(candidate_schema))
            )


def test_column_type_change_requires_new_plan(candidates_api, candidate_schema):
    plan_id = analyze(candidates_api, f"SELECT id FROM {candidate_schema}.orders WHERE region=1")
    with connect_local("demo", autocommit=True) as owner:
        owner.execute(
            sql.SQL(
                "ALTER TABLE {}.orders ALTER COLUMN region TYPE integer USING region::integer"
            ).format(sql.Identifier(candidate_schema))
        )
        try:
            response = generate(candidates_api, [plan_id])
            assert response.status_code == 409 and response.json()["error"]["code"] == "stale_plan"
        finally:
            owner.execute(
                sql.SQL("ALTER TABLE {}.orders ALTER COLUMN region TYPE bigint").format(
                    sql.Identifier(candidate_schema)
                )
            )


def test_recreated_table_requires_new_plan(candidates_api, candidate_schema):
    plan_id = analyze(candidates_api, f"SELECT id FROM {candidate_schema}.freshness WHERE id=1")
    with connect_local("demo", autocommit=True) as owner:
        owner.execute(sql.SQL("DROP TABLE {}.freshness").format(sql.Identifier(candidate_schema)))
        owner.execute(
            sql.SQL("CREATE TABLE {}.freshness(id bigint)").format(sql.Identifier(candidate_schema))
        )
        owner.execute(
            sql.SQL("GRANT SELECT ON {}.freshness TO indexpilot_analyzer").format(
                sql.Identifier(candidate_schema)
            )
        )
    response = generate(candidates_api, [plan_id])
    assert response.status_code == 409 and response.json()["error"]["code"] == "stale_plan"


def test_candidate_limit_and_multi_query_evidence(candidates_api, candidate_schema):
    plans = [
        analyze(
            candidates_api,
            f"SELECT id FROM {candidate_schema}.orders WHERE region={value} AND state='paid'",
        )
        for value in (1, 2)
    ]
    data = generate(candidates_api, plans, max_candidates=1, max_columns=2).json()
    assert len(data["proposed"]) == 1 and any(
        row["rejection_reason"] == "candidate_limit" for row in data["rejected"]
    )
    assert {row["plan_id"] for row in data["proposed"][0]["evidence"]} == set(plans)


def test_ordered_quoted_names_are_valid_postgresql_identifiers(candidates_api, candidate_schema):
    plan_id = analyze(
        candidates_api,
        f'SELECT "User;ID" FROM "{candidate_schema}"."Odd;Table" '
        'WHERE "User;ID"=1 ORDER BY "Date" DESC NULLS LAST',
    )
    data = generate(candidates_api, [plan_id]).json()
    assert data["proposed"]
    with connect_local("analyzer") as connection:
        try:
            for row in data["proposed"]:
                assert (
                    connection.execute(
                        "SELECT indexrelid FROM public.hypopg_create_index(%s)",
                        (row["definition"]["ddl"],),
                    ).fetchone()[0]
                    > 0
                )
                connection.execute("SELECT public.hypopg_reset()")
        finally:
            connection.execute("SELECT public.hypopg_reset()")


def test_empty_candidate_set_and_input_errors(candidates_api):
    client, _, _, _ = candidates_api
    plan_id = analyze(candidates_api, "SELECT 1")
    data = generate(candidates_api, [plan_id]).json()
    assert data["proposed"] == data["rejected"] == []
    assert generate(candidates_api, [str(uuid.uuid4())]).status_code == 404
    assert generate(candidates_api, [plan_id, plan_id]).status_code == 422
    assert generate(candidates_api, [plan_id], max_columns=4).status_code == 422
    assert client.get(f"/api/v1/candidates/{uuid.uuid4()}").status_code == 404


def test_inner_join_candidates_use_real_relation_columns(candidates_api, candidate_schema):
    plan_id = analyze(
        candidates_api,
        f"SELECT a.id FROM {candidate_schema}.orders a JOIN {candidate_schema}.orders b "
        "ON a.region=b.user_id WHERE a.id=1",
    )
    data = generate(candidates_api, [plan_id]).json()
    assert any(
        key_names(row) == ["region"] and any(e["reason"] == "join_lookup" for e in row["evidence"])
        for row in data["proposed"]
    )


def test_mixed_source_plans_do_not_hide_renamed_relations(candidates_api, candidate_schema):
    old = analyze(candidates_api, f"SELECT id FROM {candidate_schema}.freshness WHERE id=1")
    with connect_local("demo", autocommit=True) as owner:
        owner.execute(
            sql.SQL("ALTER TABLE {}.freshness RENAME TO freshness_renamed").format(
                sql.Identifier(candidate_schema)
            )
        )
        try:
            new = analyze(
                candidates_api, f"SELECT id FROM {candidate_schema}.freshness_renamed WHERE id=1"
            )
            response = generate(candidates_api, [new, old])
            assert response.status_code == 409 and response.json()["error"]["code"] == "stale_plan"
        finally:
            owner.execute(
                sql.SQL("ALTER TABLE {}.freshness_renamed RENAME TO freshness").format(
                    sql.Identifier(candidate_schema)
                )
            )
