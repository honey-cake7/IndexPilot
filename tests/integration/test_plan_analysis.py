import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from indexpilot.config import Settings
from indexpilot.db.connections import target_connection
from indexpilot.local import connect_local
from indexpilot.main import create_app
from indexpilot.metadata.models import PlanAnalysis, QueryPattern, QueryScenario, Workload
from indexpilot.metadata.session import metadata_engine
from indexpilot.plans.parser import walk_plan
from indexpilot.plans.service import estimate_query
from indexpilot.sql.validation import split_workload
from indexpilot.workloads.models import QueryInput
from psycopg import sql
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def planning_fixture():
    name = "m4_" + uuid.uuid4().hex[:12]
    other = "M4 Other " + name[-6:]
    with connect_local("demo", autocommit=True) as connection:
        for schema in (name, other):
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        # Test-owned namespaces only. They contain no application/demo data.
        connection.execute(sql.SQL("SET search_path TO {},pg_catalog").format(sql.Identifier(name)))
        connection.execute(
            """
          CREATE TABLE users(id bigint PRIMARY KEY,label text);
          INSERT INTO users SELECT n,'user-'||n FROM generate_series(1,100) n;
          CREATE TABLE orders(id bigint PRIMARY KEY,user_id bigint REFERENCES users(id),
            created_at timestamptz,amount numeric(12,2),status text);
          INSERT INTO orders SELECT n,1+n%100,TIMESTAMPTZ '2025-01-01 UTC'+n*INTERVAL '1 day',
             1+n%100,CASE WHEN n%2=0 THEN 'paid' ELSE 'pending' END
             FROM generate_series(1,2000) n;
          CREATE INDEX orders_lookup ON orders(user_id,created_at);
          CREATE INDEX orders_partial ON orders(user_id DESC NULLS LAST,created_at) INCLUDE(amount)
             WHERE status='paid';
          CREATE INDEX orders_expression ON orders((pg_catalog.lower(status)));
          CREATE TABLE "Odd Table"("Order ID" bigint PRIMARY KEY,"Price;quoted" numeric);
          INSERT INTO "Odd Table" VALUES(1,20);
          CREATE VIEW ordinary_view AS SELECT * FROM orders;
          CREATE MATERIALIZED VIEW materialized_view AS SELECT 1 AS id;
          CREATE TABLE secured(id bigint);
          ALTER TABLE secured ENABLE ROW LEVEL SECURITY;
          CREATE DOMAIN id_domain AS bigint;
          CREATE TABLE domain_table(id id_domain);
          CREATE TYPE state_type AS ENUM('a','b');
          CREATE TABLE enum_table(id state_type);
          CREATE TABLE generated_table(id bigint,
            computed bigint GENERATED ALWAYS AS (id+1) STORED);
          CREATE TABLE parent_table(id bigint);
          CREATE TABLE child_table() INHERITS(parent_table);
          CREATE TABLE partitioned_table(id bigint) PARTITION BY RANGE(id);
          CREATE TABLE hash_table(id bigint);
          CREATE INDEX hash_index ON hash_table USING hash(id);
          CREATE TABLE hidden_table(id bigint);
          CREATE FUNCTION bomb(bigint) RETURNS bigint LANGUAGE plpgsql IMMUTABLE
            AS $$BEGIN RAISE EXCEPTION 'unapproved function executed'; END$$;
          CREATE FUNCTION bomb_bool(bigint) RETURNS bool LANGUAGE plpgsql IMMUTABLE
            AS $$BEGIN RAISE EXCEPTION 'unapproved policy executed'; END$$;
          CREATE POLICY protected ON secured USING(bomb_bool(id));
          CREATE TABLE expression_dependency(id bigint);
          CREATE INDEX dependency_index ON expression_dependency((bomb(id)));
          CREATE TABLE constraint_dependency(id bigint CHECK(bomb_bool(id)));
          CREATE FUNCTION sum(bigint) RETURNS bigint LANGUAGE plpgsql IMMUTABLE
            AS $$BEGIN RAISE EXCEPTION 'shadow aggregate executed'; END$$;
          CREATE FUNCTION eq_bomb(bigint,bigint) RETURNS bool LANGUAGE plpgsql IMMUTABLE
            AS $$BEGIN RAISE EXCEPTION 'shadow operator executed'; END$$;
          CREATE OPERATOR = (LEFTARG=bigint,RIGHTARG=bigint,FUNCTION=eq_bomb);
          ANALYZE orders; ANALYZE users;
        """,
            prepare=False,
        )
        connection.execute(
            sql.SQL("CREATE TABLE {}.orders(id bigint PRIMARY KEY)").format(sql.Identifier(other))
        )
        for schema in (name, other):
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
        connection.execute(
            sql.SQL("REVOKE SELECT ON {}.hidden_table FROM indexpilot_analyzer").format(
                sql.Identifier(name)
            )
        )
    yield name, other
    with connect_local("demo", autocommit=True) as connection:
        for schema in (name, other):
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def plan_api(planning_fixture):
    schema, other = planning_fixture
    settings = Settings(analysis_schemas=("public", schema, other))
    ids, workloads = [], []
    with TestClient(create_app(settings)) as client:
        yield client, settings, ids, workloads
    engine = metadata_engine(settings)
    try:
        with Session(engine) as session, session.begin():
            session.execute(delete(PlanAnalysis).where(PlanAnalysis.id.in_(ids)))
            pattern_ids = select(QueryPattern.id).where(QueryPattern.workload_id.in_(workloads))
            session.execute(delete(QueryScenario).where(QueryScenario.pattern_id.in_(pattern_ids)))
            session.execute(delete(QueryPattern).where(QueryPattern.workload_id.in_(workloads)))
            session.execute(delete(Workload).where(Workload.id.in_(workloads)))
    finally:
        engine.dispose()


def submit(api, query, **values):
    client, _, ids, _ = api
    response = client.post("/api/v1/plans", json={"sql": query, **values})
    if response.status_code == 201:
        ids.append(uuid.UUID(response.json()["id"]))
    return response


def test_real_catalog_metadata(plan_api, planning_fixture):
    client, _, _, _ = plan_api
    schema, _ = planning_fixture
    data = client.get("/api/v1/schema", params={"schema_name": schema, "limit": 100}).json()
    assert data["total_tables"] >= 10
    response = client.get(
        "/api/v1/schema/table", params={"schema_name": schema, "table_name": "orders"}
    )
    assert response.status_code == 200, response.text
    table = response.json()
    assert table["estimated_rows"] == 2000 and table["total_bytes"] > 0
    assert any(c["kind"] == "f" and c["referenced_columns"] == ["id"] for c in table["constraints"])
    partial = next(index for index in table["indexes"] if index["name"] == "orders_partial")
    assert partial["predicate"] and partial["included_columns"] == ["amount"]
    assert partial["keys"][0]["descending"] and not partial["keys"][0]["nulls_first"]
    assert partial["keys"][0]["operator_class_name"] == "int8_ops"
    expression = next(index for index in table["indexes"] if index["name"] == "orders_expression")
    assert expression["expressions"] and expression["keys"][0]["column"] is None
    column = next(column for column in table["columns"] if column["name"] == "user_id")
    assert column["statistics"]["estimated_distinct_values"] == 100
    assert column["statistics"]["uniform_equality_selectivity"] == pytest.approx(0.01)
    assert column["statistics"]["most_common_values"] is None
    with_values = client.get(
        "/api/v1/schema/table",
        params={
            "schema_name": schema,
            "table_name": "orders",
            "include_values": True,
        },
    ).json()
    assert any(
        column["statistics"] and column["statistics"]["most_common_values"]
        for column in with_values["columns"]
    )


def test_real_join_predicates_sort_and_saved_history(plan_api, planning_fixture):
    schema, _ = planning_fixture
    client, _, _, _ = plan_api
    response = submit(
        plan_api,
        f'SELECT o.id,u.label FROM "{schema}".orders o '
        f'JOIN "{schema}".users u ON u.id=o.user_id '
        "WHERE o.user_id=50 AND o.created_at >= $1 ORDER BY o.created_at DESC",
        parameters={"1": {"type": "timestamptz", "value": "2025-03-01 UTC"}},
        frequency=30,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert {column["column"]["table"] for column in data["analysis"]["columns"]} == {
        "orders",
        "users",
    }
    assert {predicate["kind"] for predicate in data["analysis"]["predicates"]} >= {
        "join",
        "equality",
        "range",
    }
    assert data["analysis"]["order_by"][0]["direction"] == "desc"
    assert data["analysis"]["order_by"][0]["nulls_first"]
    assert data["plan"]["node_count"] >= 3 and not data["plan"]["execution_measured"]
    assert "Actual Rows" not in str(data["raw_explain"])
    assert data["frequency"] == 30 and "random_page_cost" in data["planner_settings"]
    assert client.get(f"/api/v1/plans/{data['id']}").json() == data
    assert any(row["id"] == data["id"] for row in client.get("/api/v1/plans?limit=100").json())


@pytest.mark.parametrize(
    "query,code",
    [
        ("SELECT id FROM {s}.orders o JOIN {s}.users u ON o.user_id=u.id", "ambiguous_column"),
        ("SELECT no_such_column FROM {s}.orders", "column_not_found"),
        ("SELECT o.id FROM {s}.orders o JOIN {s}.users o ON true", "ambiguous_relation"),
        ("SELECT orders.id FROM {s}.orders o", "column_not_found"),
        ("SELECT id FROM {s}.ordinary_view", "unsupported_relation"),
        ("SELECT id FROM {s}.materialized_view", "unsupported_relation"),
        ("SELECT id FROM {s}.secured", "unsupported_relation"),
        ("SELECT id FROM {s}.parent_table", "unsupported_relation"),
        ("SELECT id FROM {s}.child_table", "unsupported_relation"),
        ("SELECT id FROM {s}.partitioned_table", "unsupported_relation"),
        ("SELECT id FROM {s}.domain_table", "unsupported_column_type"),
        ("SELECT id FROM {s}.enum_table", "unsupported_column_type"),
        ("SELECT id FROM {s}.generated_table", "unsupported_column_type"),
        ("SELECT id FROM {s}.hash_table", "unsupported_index_dependency"),
        ("SELECT id FROM {s}.expression_dependency", "unsafe_planner_dependency"),
        ("SELECT id FROM {s}.constraint_dependency", "unsafe_planner_dependency"),
        ("SELECT id FROM {s}.orders WHERE id=$1", "missing_parameters"),
        ("SELECT id FROM {s}.orders ORDER BY id USING OPERATOR({s}.=)", "unsupported_sql"),
        ("SELECT {s}.bomb(1)", "unsafe_function"),
        ("SELECT id FROM {s}.orders ORDER BY 99", "unsupported_order_position"),
    ],
)
def test_rejects_unsafe_and_ambiguous_queries(plan_api, planning_fixture, query, code):
    schema, _ = planning_fixture
    response = submit(plan_api, query.format(s=schema))
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code


def test_permission_and_database_semantic_errors(plan_api, planning_fixture, caplog):
    schema, _ = planning_fixture
    assert submit(plan_api, f"SELECT id FROM {schema}.hidden_table").status_code == 403
    response = submit(
        plan_api,
        f"SELECT id FROM {schema}.orders WHERE id=$1",
        parameters={
            "1": {"type": "int8", "value": "private-invalid-integer"},
        },
    )
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_query"
    assert "private-invalid-integer" not in response.text + caplog.text
    assert submit(plan_api, "SELECT 1/0").status_code == 422
    assert submit(plan_api, f"SELECT id FROM {schema}.absent").status_code == 404


def test_quoted_columns_multiple_schemas_and_scope_aware_grouping(plan_api, planning_fixture):
    schema, other = planning_fixture
    response = submit(
        plan_api, f'SELECT "Order ID","Price;quoted" FROM "{schema}"."Odd Table" WHERE "Order ID"=1'
    )
    assert response.status_code == 201, response.text
    assert {column["column"]["name"] for column in response.json()["analysis"]["columns"]} == {
        "Order ID",
        "Price;quoted",
    }
    response = submit(
        plan_api, f'SELECT a.id FROM {schema}.orders a JOIN "{other}".orders b ON a.id=b.id'
    )
    assert response.status_code == 201
    assert {row["schema_name"] for row in response.json()["analysis"]["relations"]} == {
        schema,
        other,
    }
    client, _, _, workloads = plan_api
    created = client.post(
        "/api/v1/workloads/manual",
        json={
            "queries": [
                {"sql": f"SELECT id FROM {schema}.orders"},
                {"sql": f'SELECT id FROM "{other}".orders'},
            ]
        },
    ).json()
    workloads.append(uuid.UUID(created["id"]))
    assert created["pattern_total"] == 2


def test_aliases_grouping_predicate_context_and_shadowing(plan_api, planning_fixture):
    schema, _ = planning_fixture
    for query in (
        f"SELECT amount AS cost FROM {schema}.orders ORDER BY cost LIMIT 5",
        f"SELECT user_id AS customer,count(*) FROM {schema}.orders "
        "GROUP BY customer ORDER BY customer",
        f"SELECT user_id,count(*) FROM {schema}.orders GROUP BY 1 ORDER BY 1",
        f"SELECT sum(id) FROM {schema}.orders WHERE id=1::bigint",
    ):
        response = submit(plan_api, query)
        assert response.status_code == 201, response.text
        assert (
            "pg_catalog" in response.json()["analysis"]["canonical_sql"]
            or "ONLY" in response.json()["analysis"]["canonical_sql"]
        )
    response = submit(plan_api, f"SELECT id FROM {schema}.orders WHERE user_id=1 OR user_id=2")
    assert response.status_code == 201
    assert all(
        not predicate["conjunction_only"] for predicate in response.json()["analysis"]["predicates"]
    )


def test_saved_scenario_can_be_analyzed(plan_api):
    client, _, ids, workloads = plan_api
    created = client.post(
        "/api/v1/workloads/manual",
        json={
            "queries": [
                {
                    "sql": "SELECT id FROM public.orders WHERE user_id=$1",
                    "frequency": 7,
                    "parameters": {"1": {"type": "int8", "value": 101}},
                }
            ]
        },
    ).json()
    workloads.append(uuid.UUID(created["id"]))
    scenario_id = created["patterns"][0]["scenarios"][0]["id"]
    response = client.post(f"/api/v1/query-scenarios/{scenario_id}/plan")
    assert response.status_code == 201, response.text
    ids.append(uuid.UUID(response.json()["id"]))
    assert response.json()["scenario_id"] == scenario_id and response.json()["frequency"] == 7


def test_sample_workload_and_real_scan_join_types(planning_fixture):
    schema, _ = planning_fixture
    settings = Settings(analysis_schemas=("public", schema))
    with target_connection(settings) as connection:
        for statement in split_workload(Path("sample/workload.sql").read_text()):
            _, document, _ = estimate_query(connection, QueryInput(sql=statement))
            assert document.root.total_cost > 0
        # Planner switches exercise real PostgreSQL node types; they are not benchmark evidence.
        cases = [
            (
                {
                    "enable_bitmapscan": "off",
                    "enable_indexonlyscan": "off",
                    "enable_seqscan": "off",
                },
                f"SELECT * FROM {schema}.orders WHERE id=1",
                {"Index Scan"},
            ),
            (
                {
                    "enable_bitmapscan": "on",
                    "enable_indexscan": "off",
                    "enable_indexonlyscan": "off",
                    "enable_seqscan": "off",
                },
                f"SELECT * FROM {schema}.orders WHERE user_id=50",
                {"Bitmap Heap Scan", "Bitmap Index Scan"},
            ),
            (
                {
                    "enable_bitmapscan": "off",
                    "enable_indexscan": "on",
                    "enable_indexonlyscan": "on",
                    "enable_seqscan": "off",
                },
                f"SELECT id FROM {schema}.orders WHERE id=1",
                {"Index Only Scan"},
            ),
            (
                {
                    "enable_hashjoin": "on",
                    "enable_mergejoin": "off",
                    "enable_nestloop": "off",
                    "enable_seqscan": "on",
                },
                f"SELECT o.id FROM {schema}.orders o JOIN {schema}.users u ON o.user_id=u.id",
                {"Hash Join"},
            ),
            (
                {"enable_hashjoin": "off", "enable_mergejoin": "on", "enable_nestloop": "off"},
                f"SELECT o.id FROM {schema}.orders o JOIN {schema}.users u ON o.user_id=u.id",
                {"Merge Join"},
            ),
            (
                {"enable_hashjoin": "off", "enable_mergejoin": "off", "enable_nestloop": "on"},
                f"SELECT o.id FROM {schema}.orders o JOIN {schema}.users u "
                "ON o.user_id=u.id WHERE o.id=1",
                {"Nested Loop"},
            ),
        ]
        for switches, query, expected in cases:
            for name, value in switches.items():
                connection.execute("SELECT set_config(%s,%s,true)", (name, value))
            _, document, _ = estimate_query(
                connection, QueryInput(sql=query), allowed_schemas=settings.analysis_schemas
            )
            assert expected <= {node.node_type for _, node in walk_plan(document.root)}


def test_sequential_scan_explanation_and_schema_boundaries(plan_api):
    response = submit(plan_api, "SELECT id FROM public.orders WHERE status='paid'")
    assert response.status_code == 201
    observations = response.json()["plan"]["observations"]
    assert any(
        item["node_type"] == "Seq Scan" and "not automatically" in item["message"]
        for item in observations
    )
    client, _, _, _ = plan_api
    assert client.get("/api/v1/schema?schema_name=pg_catalog").status_code == 422
    assert client.get(f"/api/v1/plans/{uuid.uuid4()}").status_code == 404


def test_no_analyzer_side_effects_on_rejected_function(plan_api, planning_fixture):
    schema, _ = planning_fixture
    response = submit(plan_api, f"SELECT {schema}.bomb(1)")
    assert response.status_code == 422 and response.json()["error"]["code"] == "unsafe_function"
    # If the function had run, its exception would have produced a different error.
    assert "unapproved function executed" not in response.text
