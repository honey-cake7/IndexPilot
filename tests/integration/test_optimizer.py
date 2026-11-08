import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from indexpilot.db.connections import target_connection
from indexpilot.evaluation.context import prepare_context
from indexpilot.evaluation.engine import EvaluationBudget, WorkloadEvaluator
from indexpilot.evaluation.persistence import get_run
from indexpilot.evaluation.session import HypotheticalSession
from indexpilot.local import connect_local
from indexpilot.main import create_app
from indexpilot.metadata.models import (
    EvaluationRun,
    IndexCandidate,
    OptimizationCandidate,
    OptimizationRun,
)
from indexpilot.optimizer.persistence import get_optimization, save_optimization
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.integration.test_hypopg_evaluation import admin as admin
from tests.integration.test_hypopg_evaluation import batch, load_context
from tests.integration.test_hypopg_evaluation import evaluation_api as evaluation_api
from tests.integration.test_hypopg_evaluation import evaluation_schema as evaluation_schema

pytestmark = pytest.mark.integration


def post(api, batch_id, **options):
    return api[0].post(
        "/api/v1/optimizations",
        json={"batch_id": batch_id, "storage_budget_bytes": 100_000_000, **options},
    )


def one_candidate(api, schema):
    source = batch(api, schema)
    response = api[0].post(
        "/api/v1/candidates", json={"plan_ids": source["source_plan_ids"], "max_candidates": 1}
    )
    assert response.status_code == 201, response.text
    result = response.json()
    api[4].append(uuid.UUID(result["id"]))
    assert len(result["proposed"]) == 1
    return result


def test_real_selection_trace_weighted_objective_and_history(evaluation_api, evaluation_schema):
    proposed = batch(evaluation_api, evaluation_schema, two_queries=True)
    with connect_local("analyzer") as connection:
        before = connection.execute(
            "SELECT count(*) FROM pg_index WHERE indrelid=%s::regclass",
            (f"{evaluation_schema}.orders",),
        ).fetchone()[0]
    response = post(evaluation_api, proposed["id"], max_query_regression_pct=0)
    assert response.status_code == 201, response.text
    data = response.json()
    result = data["result"]
    assert result["selected_candidate_ids"] and result["final_verified"]
    assert data["cleanup_confirmed"]
    assert result["final_score"]["storage_bytes"] <= data["options"]["storage_budget_bytes"]
    assert result["final_score"]["read_cost"] < result["baseline_score"]["read_cost"]
    assert result["final_score"]["write_penalty"] == 0
    assert result["final_score"]["read_cost"] == pytest.approx(
        sum(
            query["frequency"] * query["plan"]["root"]["total_cost"]
            for query in result["final"]["queries"]
        )
    )
    assert result["evaluations"] == len(result["trials"]) + 2
    chosen = [trial for trial in result["trials"] if trial["chosen"]]
    assert len(chosen) == len(result["selected_candidate_ids"])
    selected = set()
    objective = result["baseline_score"]["objective"]
    for trial in chosen:
        selected.add(trial["added_candidate_id"])
        assert set(trial["candidate_ids"]) == selected
        assert trial["score"]["storage_bytes"] <= data["options"]["storage_budget_bytes"]
        assert trial["marginal_net_gain"] == pytest.approx(objective - trial["score"]["objective"])
        assert trial["gain_per_byte"] > 0 and trial["score"]["feasible"]
        objective = trial["score"]["objective"]
    assert any(query["used_candidate_ids"] for query in result["final"]["queries"])
    assert all(
        "Actual Rows" not in str(query["raw_explain"]) for query in result["final"]["queries"]
    )
    assert evaluation_api[0].get(f"/api/v1/optimizations/{data['id']}").json() == data
    with TestClient(create_app(evaluation_api[1])) as second:
        assert second.get(f"/api/v1/optimizations/{data['id']}").json() == data
    assert data["id"] in [
        row["id"] for row in evaluation_api[0].get("/api/v1/optimizations").json()
    ]
    with connect_local("analyzer") as connection:
        assert connection.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT count(*) FROM pg_index WHERE indrelid=%s::regclass",
                (f"{evaluation_schema}.orders",),
            ).fetchone()[0]
            == before
        )


def test_real_exact_budget_and_one_byte_below(evaluation_api, evaluation_schema):
    proposed = one_candidate(evaluation_api, evaluation_schema)
    evidence = evaluation_api[0].post("/api/v1/evaluations", json={"batch_id": proposed["id"]})
    assert evidence.status_code == 201, evidence.text
    size = evidence.json()["trials"][0]["estimated_size_bytes"]
    assert size > 0
    for budget, selected in [(size, True), (size - 1, False), (0, False)]:
        response = post(evaluation_api, proposed["id"], storage_budget_bytes=budget)
        assert response.status_code == 201, response.text
        result = response.json()["result"]
        assert bool(result["selected_candidate_ids"]) is selected
        assert result["final_score"]["storage_bytes"] <= budget


def test_real_unknown_size_cannot_enter_selection(evaluation_api, evaluation_schema, admin):
    proposed = one_candidate(evaluation_api, evaluation_schema)
    admin.execute("REVOKE EXECUTE ON FUNCTION public.hypopg_relation_size(oid) FROM PUBLIC")
    try:
        response = post(evaluation_api, proposed["id"])
        assert response.status_code == 201, response.text
        result = response.json()["result"]
        assert result["selected_candidate_ids"] == []
        assert result["trials"][0]["reason"] == "unknown_storage"
    finally:
        admin.execute("GRANT EXECUTE ON FUNCTION public.hypopg_relation_size(oid) TO PUBLIC")


def test_inaccessible_hypopg_saves_only_unavailable_evidence(
    evaluation_api, evaluation_schema, admin
):
    proposed = one_candidate(evaluation_api, evaluation_schema)
    admin.execute("REVOKE EXECUTE ON FUNCTION public.hypopg_create_index(text) FROM PUBLIC")
    try:
        response = post(evaluation_api, proposed["id"])
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == "hypopg_unavailable"
        with Session(evaluation_api[2]) as db:
            run = db.scalar(
                select(EvaluationRun).where(EvaluationRun.batch_id == uuid.UUID(proposed["id"]))
            )
            assert run.status == "unavailable"
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(OptimizationRun)
                    .where(OptimizationRun.evaluation_run_id == run.id)
                )
                == 0
            )
        assert get_run(evaluation_api[2], run.id).baseline is None
    finally:
        admin.execute("GRANT EXECUTE ON FUNCTION public.hypopg_create_index(text) TO PUBLIC")


def test_real_optional_write_penalty_and_search_limits(evaluation_api, evaluation_schema):
    proposed = one_candidate(evaluation_api, evaluation_schema)
    penalized = post(evaluation_api, proposed["id"], write_penalty_cost_per_mib=1e12)
    assert penalized.status_code == 201, penalized.text
    assert penalized.json()["result"]["selected_candidate_ids"] == []
    assert penalized.json()["result"]["trials"][0]["reason"] == "nonpositive_net_gain"
    limited = post(evaluation_api, proposed["id"], max_evaluations=2)
    assert limited.status_code == 201, limited.text
    result = limited.json()["result"]
    assert result["stop_reason"] == "evaluation_limit" and result["evaluations"] == 2
    assert result["selected_candidate_ids"] == [] and result["final_verified"]


def test_fresh_evaluation_really_bypasses_the_session_cache(evaluation_api, evaluation_schema):
    proposed = one_candidate(evaluation_api, evaluation_schema)
    sources, stored = load_context(evaluation_api, proposed["id"])
    settings = evaluation_api[1]
    with (
        target_connection(settings, repeatable_read=True) as connection,
        HypotheticalSession(connection) as hypo,
    ):
        budget = EvaluationBudget(connection, seconds=30, statement_timeout_ms=5000)
        queries, compiled = prepare_context(
            connection,
            sources,
            stored,
            allowed_schemas=settings.analysis_schemas,
            check=budget.check,
        )
        evaluator = WorkloadEvaluator(connection, hypo, queries, compiled, budget)
        key = frozenset(compiled)
        first = evaluator.evaluate(key)
        # Deliberate cache corruption distinguishes a fresh server EXPLAIN from a cache hit.
        evaluator.cache.values[key].queries[0].plan.root.total_cost = 999999999
        assert evaluator.evaluate(key).queries[0].plan.root.total_cost == 999999999
        fresh = evaluator.evaluate(key, refresh=True)
        assert fresh.queries[0].plan.root.total_cost == first.queries[0].plan.root.total_cost
        assert connection.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 0
    assert hypo.cleanup_confirmed


def test_optimizer_and_evidence_save_roll_back_together(evaluation_api, evaluation_schema):
    proposed = one_candidate(evaluation_api, evaluation_schema)
    response = post(evaluation_api, proposed["id"])
    assert response.status_code == 201, response.text
    engine = evaluation_api[2]
    saved = get_optimization(engine, uuid.UUID(response.json()["id"]))
    evidence = get_run(engine, saved.evaluation_run_id)
    result = saved.result.model_copy(deep=True)
    result.candidates.append(result.candidates[0].model_copy())
    with Session(engine) as db:
        before = db.scalar(select(func.count()).select_from(EvaluationRun))
    with pytest.raises(IntegrityError):
        save_optimization(
            engine,
            result=result,
            options=saved.options,
            evidence=dict(
                batch_id=saved.batch_id,
                status="completed",
                capability=evidence.capability,
                requested_sets=evidence.requested_sets,
                context=evidence.context,
                queries=evidence.queries,
                results=[evidence.baseline, *evidence.trials],
                warnings=[],
                error_code=None,
                cleanup_confirmed=True,
            ),
        )
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(EvaluationRun)) == before
    assert get_optimization(engine, saved.id) == saved


def test_database_rejects_selected_candidate_without_position(evaluation_api, evaluation_schema):
    proposed = one_candidate(evaluation_api, evaluation_schema)
    response = post(evaluation_api, proposed["id"], max_selected_indexes=0)
    assert response.status_code == 201, response.text
    identifier = uuid.UUID(response.json()["id"])
    with pytest.raises(IntegrityError), Session(evaluation_api[2]) as db, db.begin():
        row = db.scalar(
            select(OptimizationCandidate).where(OptimizationCandidate.run_id == identifier)
        )
        row.selected = True
        row.selection_order = None
        db.flush()


def test_optimization_api_validation_and_empty_batch(evaluation_api):
    proposed = batch(evaluation_api, "unused", query={"sql": "SELECT 1 WHERE false"})
    for values in [
        {"storage_budget_bytes": -1},
        {"storage_budget_bytes": True},
        {"max_evaluations": 1},
        {"write_penalty_cost_per_mib": -1},
        {"write_weights": {str(uuid.uuid4()): 1}},
    ]:
        assert post(evaluation_api, proposed["id"], **values).status_code == 422
    response = post(evaluation_api, proposed["id"])
    assert response.status_code == 201, response.text
    result = response.json()["result"]
    assert result["stop_reason"] == "no_candidates" and result["selected_candidate_ids"] == []
    assert result["final_score"]["storage_bytes"] == 0
    assert evaluation_api[0].get(f"/api/v1/optimizations/{uuid.uuid4()}").status_code == 404


def test_invalid_saved_ddl_fails_safely_without_partial_selection(
    evaluation_api, evaluation_schema, caplog
):
    proposed = one_candidate(evaluation_api, evaluation_schema)
    candidate = proposed["proposed"][0]
    definition = dict(candidate["definition"], ddl="SELECT 'm7_private_marker'")
    with Session(evaluation_api[2]) as db, db.begin():
        db.execute(
            update(IndexCandidate)
            .where(IndexCandidate.id == uuid.UUID(candidate["id"]))
            .values(definition=definition)
        )
    response = post(evaluation_api, proposed["id"])
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "invalid_candidate"
    assert "m7_private_marker" not in response.text + caplog.text
    with Session(evaluation_api[2]) as db:
        run = db.scalar(
            select(EvaluationRun).where(EvaluationRun.batch_id == uuid.UUID(proposed["id"]))
        )
        assert run.status == "failed" and run.cleanup_confirmed
        assert (
            db.scalar(
                select(func.count())
                .select_from(OptimizationRun)
                .where(OptimizationRun.evaluation_run_id == run.id)
            )
            == 0
        )
    failed = get_run(evaluation_api[2], run.id)
    assert failed.baseline is None and failed.trials == []


def test_parallel_history_reads_work_with_one_metadata_connection(
    evaluation_api, evaluation_schema
):
    proposed = one_candidate(evaluation_api, evaluation_schema)
    response = post(evaluation_api, proposed["id"])
    assert response.status_code == 201, response.text
    identifier = uuid.UUID(response.json()["id"])
    # Nested retrieval must join the held connection rather than wait on a second checkout.
    small_pool = create_engine(
        evaluation_api[2].url, pool_size=1, max_overflow=0, pool_timeout=2, hide_parameters=True
    )
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(
                executor.map(lambda _: get_optimization(small_pool, identifier), range(4))
            )
        assert all(result.model_dump(mode="json") == response.json() for result in results)
    finally:
        small_pool.dispose()
