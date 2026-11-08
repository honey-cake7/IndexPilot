import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from indexpilot.local import connect_local
from indexpilot.main import create_app
from indexpilot.metadata.models import (
    EvaluationQuery,
    IndexCandidate,
    OptimizationRun,
    RecommendationIndexQuery,
    RecommendationQuery,
    RecommendationSet,
    RecommendationSetIndex,
)
from indexpilot.recommendations.models import RecommendationRequest
from indexpilot.recommendations.persistence import get_recommendation
from indexpilot.recommendations.service import create_recommendation
from pglast import ast, parse_sql
from psycopg import sql
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.integration.test_hypopg_evaluation import batch
from tests.integration.test_hypopg_evaluation import evaluation_api as evaluation_api
from tests.integration.test_hypopg_evaluation import evaluation_schema as evaluation_schema
from tests.integration.test_optimizer import post

pytestmark = pytest.mark.integration


def optimization(api, schema, **options):
    proposed = batch(api, schema, two_queries=True)
    response = post(api, proposed["id"], **options)
    assert response.status_code == 201, response.text
    return response.json()


def recommend(api, source):
    response = api[0].post("/api/v1/recommendations", json={"optimization_id": source["id"]})
    assert response.status_code in (200, 201), response.text
    return response


def test_real_recommendations_plans_attribution_and_restart_history(
    evaluation_api, evaluation_schema
):
    source = optimization(evaluation_api, evaluation_schema)
    response = recommend(evaluation_api, source)
    assert response.status_code == 201
    data = response.json()
    assert data["indexes"] and len(data["queries"]) == 2
    assert data["summary"]["baseline_score"] == source["result"]["baseline_score"]
    assert data["evidence_level"] == "planner_estimate" and not data["execution_measured"]
    assert data["benchmark_outcome"] is None
    assert [item["candidate_id"] for item in data["indexes"]] == source["result"][
        "selected_candidate_ids"
    ]
    assert (
        sum(item["estimated_size_bytes"] for item in data["indexes"])
        == data["summary"]["estimated_size_bytes"]
    )
    baseline = source["result"]["baseline_score"]["read_cost"]
    for query in data["queries"]:
        assert query["statistics_observations"]
        assert all(
            "last_analyze" in item and "last_autoanalyze" in item
            for item in query["statistics_observations"]
        )
        explanation = query["explanation"]
        assert explanation["baseline_cost"] == query["baseline_plan"]["root"]["total_cost"]
        assert explanation["final_cost"] == query["hypothetical_plan"]["root"]["total_cost"]
        assert explanation["estimated_weighted_cost_reduction"] == pytest.approx(
            query["frequency"] * (explanation["baseline_cost"] - explanation["final_cost"])
        )
        assert explanation["contribution_to_baseline_pct"] == pytest.approx(
            100 * explanation["estimated_weighted_cost_reduction"] / baseline
        )
    assert sum(
        query["explanation"]["contribution_to_baseline_pct"] for query in data["queries"]
    ) == pytest.approx(data["summary"]["estimated_read_improvement_pct"])
    for item in data["indexes"]:
        assert "ddl" not in item["definition"]
        assert (
            item["relevant_queries"]
            and item["explanation"]["attribution"] == "selection_step_marginal"
        )
        assert any(link["proposed_evidence"] for link in item["relevant_queries"])
    assert recommend(evaluation_api, source).status_code == 200
    with TestClient(create_app(evaluation_api[1])) as second:
        assert second.get(f"/api/v1/recommendations/{data['id']}").json() == data
    history = (
        evaluation_api[0]
        .get(f"/api/v1/recommendations?optimization_id={source['id']}&limit=1")
        .json()
    )
    assert len(history) == 1 and history[0]["id"] == data["id"]


def test_snapshot_and_sql_survive_source_metadata_changes(evaluation_api, evaluation_schema):
    source = optimization(evaluation_api, evaluation_schema)
    data = recommend(evaluation_api, source).json()
    endpoint = f"/api/v1/recommendations/{data['id']}"
    artifact = evaluation_api[0].get(endpoint + "/deployment-sql").json()
    with Session(evaluation_api[2]) as db, db.begin():
        db.execute(
            update(OptimizationRun)
            .where(OptimizationRun.id == uuid.UUID(source["id"]))
            .values(options={"changed": True}, summary={"changed": True})
        )
        db.execute(
            update(IndexCandidate)
            .where(
                IndexCandidate.id.in_([uuid.UUID(item["candidate_id"]) for item in data["indexes"]])
            )
            .values(definition={"changed": True})
        )
        db.execute(
            update(EvaluationQuery)
            .where(EvaluationQuery.run_id == uuid.UUID(source["evaluation_run_id"]))
            .values(analysis={"changed": True})
        )
    assert evaluation_api[0].get(endpoint).json() == data
    assert evaluation_api[0].get(endpoint + "/deployment-sql").json() == artifact
    assert recommend(evaluation_api, source).json() == data


def test_invalid_source_rolls_back_all_snapshot_rows(evaluation_api, evaluation_schema, caplog):
    source = optimization(evaluation_api, evaluation_schema)
    selected = uuid.UUID(source["result"]["selected_candidate_ids"][0])
    with Session(evaluation_api[2]) as db, db.begin():
        row = db.get(IndexCandidate, selected)
        row.definition = dict(row.definition, ddl="SELECT 'm8_private_marker'")
    models = (
        RecommendationSet,
        RecommendationSetIndex,
        RecommendationQuery,
        RecommendationIndexQuery,
    )
    with Session(evaluation_api[2]) as db:
        before = [db.scalar(select(func.count()).select_from(model)) for model in models]
    response = evaluation_api[0].post(
        "/api/v1/recommendations", json={"optimization_id": source["id"]}
    )
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "invalid_recommendation_source"
    )
    assert "m8_private_marker" not in response.text + caplog.text
    with Session(evaluation_api[2]) as db:
        assert [db.scalar(select(func.count()).select_from(model)) for model in models] == before


def test_snapshot_creation_does_not_require_target_select(evaluation_api, evaluation_schema):
    source = optimization(evaluation_api, evaluation_schema)
    with connect_local("demo", autocommit=True) as owner:
        owner.execute(
            sql.SQL("REVOKE SELECT ON {}.orders FROM indexpilot_analyzer").format(
                sql.Identifier(evaluation_schema)
            )
        )
        try:
            data = recommend(evaluation_api, source).json()
            assert data["indexes"]
            assert evaluation_api[0].get(f"/api/v1/recommendations/{data['id']}").status_code == 200
        finally:
            owner.execute(
                sql.SQL("GRANT SELECT ON {}.orders TO indexpilot_analyzer").format(
                    sql.Identifier(evaluation_schema)
                )
            )


def test_concurrent_duplicate_saves_and_single_connection_history(
    evaluation_api, evaluation_schema
):
    source = optimization(evaluation_api, evaluation_schema)
    body = RecommendationRequest(optimization_id=source["id"])
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(lambda _: create_recommendation(evaluation_api[2], body), range(4))
        )
    assert sum(created for _, created in results) == 1
    assert len({result.id for result, _ in results}) == 1
    small = create_engine(
        evaluation_api[2].url, pool_size=1, max_overflow=0, pool_timeout=2, hide_parameters=True
    )
    try:
        assert get_recommendation(small, results[0][0].id) == results[0][0]
    finally:
        small.dispose()


def test_composite_foreign_keys_reject_cross_recommendation_query(
    evaluation_api, evaluation_schema
):
    first = recommend(evaluation_api, optimization(evaluation_api, evaluation_schema)).json()
    second = recommend(evaluation_api, optimization(evaluation_api, evaluation_schema)).json()
    with pytest.raises(IntegrityError), Session(evaluation_api[2]) as db, db.begin():
        db.add(
            RecommendationIndexQuery(
                recommendation_id=uuid.UUID(first["id"]),
                candidate_id=uuid.UUID(first["indexes"][0]["candidate_id"]),
                source_plan_id=uuid.UUID(second["queries"][0]["source_plan_id"]),
                proposed_evidence=[],
                used_in_final_plan=False,
            )
        )
        db.flush()


@pytest.mark.parametrize(
    "field,value", [("estimated_size_bytes", 0), ("selection_order", 0), ("selection_order", 33)]
)
def test_index_snapshot_constraints(evaluation_api, evaluation_schema, field, value):
    data = recommend(evaluation_api, optimization(evaluation_api, evaluation_schema)).json()
    with pytest.raises(IntegrityError), Session(evaluation_api[2]) as db, db.begin():
        row = db.scalar(
            select(RecommendationSetIndex).where(
                RecommendationSetIndex.recommendation_id == uuid.UUID(data["id"])
            )
        )
        setattr(row, field, value)
        db.flush()


def test_empty_selection_and_invalid_requests(evaluation_api, evaluation_schema):
    source = optimization(evaluation_api, evaluation_schema, storage_budget_bytes=0)
    data = recommend(evaluation_api, source).json()
    assert data["indexes"] == [] and data["summary"]["estimated_size_bytes"] == 0
    url = f"/api/v1/recommendations/{data['id']}"
    assert evaluation_api[0].get(url + "/deployment-sql").json()["statements"] == []
    assert "CREATE INDEX" not in evaluation_api[0].get(url + "/deployment.sql").text
    for path in [
        f"/api/v1/recommendations/{uuid.uuid4()}",
        f"/api/v1/recommendations/{uuid.uuid4()}/deployment-sql",
    ]:
        assert evaluation_api[0].get(path).status_code == 404
    assert (
        evaluation_api[0]
        .post("/api/v1/recommendations", json={"optimization_id": str(uuid.uuid4())})
        .status_code
        == 404
    )
    assert (
        evaluation_api[0]
        .post(
            "/api/v1/recommendations",
            json={"optimization_id": source["id"], "sql": "CREATE INDEX arbitrary"},
        )
        .status_code
        == 422
    )
    assert evaluation_api[0].patch(url, json={"name": "changed"}).status_code == 405


def test_export_quotes_real_identifiers_and_never_creates_index(evaluation_api, evaluation_schema):
    name = 'orders " ; -- Unicode'
    qualified = sql.Identifier(evaluation_schema, name)
    with connect_local("demo", autocommit=True) as owner:
        owner.execute(
            sql.SQL("CREATE TABLE {} (LIKE {}.orders INCLUDING ALL)").format(
                qualified, sql.Identifier(evaluation_schema)
            )
        )
        owner.execute(
            sql.SQL("INSERT INTO {} SELECT * FROM {}.orders").format(
                qualified, sql.Identifier(evaluation_schema)
            )
        )
        owner.execute(sql.SQL("ANALYZE {}").format(qualified))
        owner.execute(sql.SQL("GRANT SELECT ON {} TO indexpilot_analyzer").format(qualified))
        before = owner.execute(
            "SELECT count(*) FROM pg_index WHERE indrelid=%s::regclass", (qualified.as_string(),)
        ).fetchone()[0]
    proposed = batch(
        evaluation_api,
        evaluation_schema,
        query={
            "sql": sql.SQL("SELECT id FROM {} WHERE user_id=42").format(qualified).as_string(),
            "frequency": 100,
        },
    )
    response = post(evaluation_api, proposed["id"])
    assert response.status_code == 201, response.text
    data = recommend(evaluation_api, response.json()).json()
    url = f"/api/v1/recommendations/{data['id']}"
    artifact = evaluation_api[0].get(url + "/deployment-sql").json()
    assert artifact["executed"] is False and artifact["requires_human_review"]
    assert artifact["statements"]
    for statement in artifact["statements"]:
        nodes = parse_sql(statement["sql"])
        assert len(nodes) == 1 and isinstance(nodes[0].stmt, ast.IndexStmt)
        assert nodes[0].stmt.relation.relname == name
        assert nodes[0].stmt.relation.schemaname == evaluation_schema
    download = evaluation_api[0].get(url + "/deployment.sql")
    assert download.status_code == 200 and "attachment" in download.headers["content-disposition"]
    assert len(parse_sql(download.text)) == len(artifact["statements"])
    with connect_local("demo", autocommit=True) as owner:
        assert (
            owner.execute(
                "SELECT count(*) FROM pg_index WHERE indrelid=%s::regclass",
                (qualified.as_string(),),
            ).fetchone()[0]
            == before
        )
