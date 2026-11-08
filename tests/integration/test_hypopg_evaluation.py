import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from fastapi.testclient import TestClient
from indexpilot.candidates.models import CandidateDefinition
from indexpilot.config import Settings
from indexpilot.db.connections import target_connection
from indexpilot.errors import DomainError
from indexpilot.evaluation.context import SourceQuery, prepare_context
from indexpilot.evaluation.engine import EvaluationBudget, WorkloadEvaluator
from indexpilot.evaluation.models import EvaluationRequest
from indexpilot.evaluation.service import evaluate_batch
from indexpilot.evaluation.session import HypoPGUnavailable, HypotheticalSession
from indexpilot.local import ROLES, connect_local
from indexpilot.main import create_app
from indexpilot.metadata.models import (
    CandidateBatch,
    CandidateBatchSource,
    EvaluationMember,
    EvaluationPlan,
    EvaluationQuery,
    EvaluationRun,
    IndexCandidate,
    IndexCandidateEvidence,
    IndexEvaluation,
    OptimizationCandidate,
    OptimizationRun,
    OptimizationTrial,
    PlanAnalysis,
    RecommendationIndexQuery,
    RecommendationQuery,
    RecommendationSet,
    RecommendationSetIndex,
)
from indexpilot.metadata.session import metadata_engine
from indexpilot.sql.models import SQLAnalysis
from psycopg import sql
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def evaluation_schema():
    schema = "m6_" + uuid.uuid4().hex[:12]
    with connect_local("demo", autocommit=True) as owner:
        owner.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("SET search_path TO {},pg_catalog").format(sql.Identifier(schema)))
        owner.execute(
            """
          CREATE TABLE orders(id bigint PRIMARY KEY,user_id bigint,
            created_at timestamptz,status text);
          INSERT INTO orders SELECT n,n%1000,TIMESTAMPTZ '2025-01-01 UTC'+n*INTERVAL '1 second',
            CASE WHEN n%2=0 THEN 'paid' ELSE 'pending' END FROM generate_series(1,20000) n;
          ANALYZE orders;
        """,
            prepare=False,
        )
        owner.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO indexpilot_analyzer").format(
                sql.Identifier(schema)
            )
        )
        owner.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO indexpilot_analyzer").format(
                sql.Identifier(schema)
            )
        )
    yield schema
    with connect_local("demo", autocommit=True) as owner:
        owner.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def evaluation_api(evaluation_schema):
    settings = Settings(analysis_schemas=("public", evaluation_schema))
    engine = metadata_engine(settings)
    plan_ids = []
    batch_ids = []
    with TestClient(create_app(settings)) as client:
        yield client, settings, engine, plan_ids, batch_ids
    try:
        with Session(engine) as db, db.begin():
            runs = select(EvaluationRun.id).where(EvaluationRun.batch_id.in_(batch_ids))
            sets = select(IndexEvaluation.id).where(IndexEvaluation.run_id.in_(runs))
            candidates = select(IndexCandidate.id).where(IndexCandidate.batch_id.in_(batch_ids))
            optimizations = select(OptimizationRun.id).where(
                OptimizationRun.evaluation_run_id.in_(runs)
            )
            recommendations = select(RecommendationSet.id).where(
                RecommendationSet.optimization_id.in_(optimizations)
            )
            for model in (RecommendationIndexQuery, RecommendationSetIndex, RecommendationQuery):
                db.execute(delete(model).where(model.recommendation_id.in_(recommendations)))
            db.execute(delete(RecommendationSet).where(RecommendationSet.id.in_(recommendations)))
            db.execute(delete(OptimizationTrial).where(OptimizationTrial.run_id.in_(optimizations)))
            db.execute(
                delete(OptimizationCandidate).where(OptimizationCandidate.run_id.in_(optimizations))
            )
            db.execute(delete(OptimizationRun).where(OptimizationRun.id.in_(optimizations)))
            db.execute(delete(EvaluationPlan).where(EvaluationPlan.evaluation_id.in_(sets)))
            db.execute(delete(EvaluationMember).where(EvaluationMember.evaluation_id.in_(sets)))
            db.execute(delete(IndexEvaluation).where(IndexEvaluation.run_id.in_(runs)))
            db.execute(delete(EvaluationQuery).where(EvaluationQuery.run_id.in_(runs)))
            db.execute(delete(EvaluationRun).where(EvaluationRun.id.in_(runs)))
            db.execute(
                delete(IndexCandidateEvidence).where(
                    IndexCandidateEvidence.candidate_id.in_(candidates)
                )
            )
            db.execute(delete(IndexCandidate).where(IndexCandidate.batch_id.in_(batch_ids)))
            db.execute(
                delete(CandidateBatchSource).where(CandidateBatchSource.batch_id.in_(batch_ids))
            )
            db.execute(delete(CandidateBatch).where(CandidateBatch.id.in_(batch_ids)))
            db.execute(delete(PlanAnalysis).where(PlanAnalysis.id.in_(plan_ids)))
    finally:
        engine.dispose()


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setitem(ROLES, "m6_admin", ("indexpilot_demo", "postgres", "admin_password"))
    with connect_local("m6_admin", autocommit=True) as connection:
        yield connection


def batch(api, schema, *, two_queries=False, query=None):
    client, _, _, plan_ids, batch_ids = api
    inputs = [
        query
        or dict(
            sql=f"SELECT id,status FROM {schema}.orders WHERE user_id=$1 "
            "AND created_at >= $2 ORDER BY created_at DESC",
            frequency=100,
            parameters={
                "1": {"type": "int8", "value": 42},
                "2": {"type": "timestamptz", "value": "2025-01-01T01:00:00+00:00"},
            },
        )
    ]
    if two_queries:
        inputs.append(dict(sql=f"SELECT id FROM {schema}.orders WHERE user_id=73", frequency=5))
    ids = []
    for body in inputs:
        response = client.post("/api/v1/plans", json=body)
        assert response.status_code == 201, response.text
        identifier = uuid.UUID(response.json()["id"])
        plan_ids.append(identifier)
        ids.append(str(identifier))
    response = client.post("/api/v1/candidates", json={"plan_ids": ids})
    assert response.status_code == 201, response.text
    result = response.json()
    batch_ids.append(uuid.UUID(result["id"]))
    return result


def singleton(result):
    return next(
        row
        for row in result["proposed"]
        if [key["column"] for key in row["definition"]["keys"]] == ["user_id"]
    )


def load_context(api, batch_id):
    _, _, engine, _, _ = api
    with Session(engine) as db:
        sources = [
            SourceQuery(row.id, row.frequency, SQLAnalysis.model_validate(row.analysis))
            for row in db.scalars(
                select(PlanAnalysis)
                .join(CandidateBatchSource, CandidateBatchSource.plan_id == PlanAnalysis.id)
                .where(CandidateBatchSource.batch_id == uuid.UUID(batch_id))
                .order_by(PlanAnalysis.id)
            )
        ]
        stored = {
            row.id: row.definition
            for row in db.scalars(
                select(IndexCandidate).where(
                    IndexCandidate.batch_id == uuid.UUID(batch_id),
                    IndexCandidate.status == "proposed",
                )
            )
        }
    return sources, stored


def test_real_workload_sets_fresh_baseline_storage_and_reload(evaluation_api, evaluation_schema):
    client, _, engine, plan_ids, _ = evaluation_api
    proposed = batch(evaluation_api, evaluation_schema, two_queries=True)
    # Test-owned historical summaries deliberately differ: evaluator must replan, not reuse them.
    with Session(engine) as db, db.begin():
        db.execute(
            update(PlanAnalysis)
            .where(PlanAnalysis.id.in_(plan_ids))
            .values(total_cost=0, raw_explain=[{"Plan": {"Node Type": "Result", "Total Cost": 0}}])
        )
    with connect_local("analyzer") as connection:
        before = connection.execute(
            "SELECT count(*) FROM pg_index WHERE indrelid=%s::regclass",
            (f"{evaluation_schema}.orders",),
        ).fetchone()[0]
    response = client.post("/api/v1/evaluations", json={"batch_id": proposed["id"]})
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "completed" and data["cleanup_confirmed"]
    assert len(data["trials"]) == len(proposed["proposed"]) + 1
    assert data["baseline"]["weighted_cost"] > 0
    assert len(data["baseline"]["queries"]) == 2
    assert data["baseline"]["weighted_cost"] == pytest.approx(
        sum(
            row["frequency"] * row["plan"]["root"]["total_cost"]
            for row in data["baseline"]["queries"]
        )
    )
    combined = next(
        row for row in data["trials"] if len(row["candidate_ids"]) == len(proposed["proposed"])
    )
    assert combined["weighted_cost"] < data["baseline"]["weighted_cost"]
    assert combined["storage_complete"] and combined["estimated_size_bytes"] > 0
    assert combined["estimated_size_bytes"] == sum(
        row["estimated_size_bytes"] for row in combined["indexes"]
    )
    assert all(row["plan"]["execution_measured"] is False for row in combined["queries"])
    assert any(row["used_candidate_ids"] for row in combined["queries"])
    assert all("Actual Rows" not in str(row["raw_explain"]) for row in combined["queries"])
    assert client.get(f"/api/v1/evaluations/{data['id']}").json() == data
    with TestClient(create_app(evaluation_api[1])) as second:
        assert second.get(f"/api/v1/evaluations/{data['id']}").json() == data
    assert (
        client.get(f"/api/v1/evaluations?batch_id={proposed['id']}").json()[0]["id"] == data["id"]
    )
    with connect_local("analyzer") as connection:
        assert connection.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT count(*) FROM pg_index WHERE indrelid=%s::regclass",
                (f"{evaluation_schema}.orders",),
            ).fetchone()[0]
            == before
        )


def test_combined_benefit_is_not_added_singleton_benefit(evaluation_api, evaluation_schema):
    proposed = batch(evaluation_api, evaluation_schema)
    alternatives = [
        row["id"]
        for row in proposed["proposed"]
        if [key["column"] for key in row["definition"]["keys"]] == ["user_id", "created_at"]
    ]
    assert len(alternatives) >= 2
    a, b = alternatives[:2]
    response = evaluation_api[0].post(
        "/api/v1/evaluations",
        json={"batch_id": proposed["id"], "candidate_sets": [[a], [b], [a, b]]},
    )
    assert response.status_code == 201, response.text
    trials = response.json()["trials"]
    singles = [row["estimated_improvement_pct"] for row in trials if len(row["candidate_ids"]) == 1]
    combined = next(row for row in trials if len(row["candidate_ids"]) == 2)
    assert all(value > 0 for value in singles)
    assert combined["estimated_improvement_pct"] != pytest.approx(sum(singles))


def test_two_held_sessions_are_isolated_and_rollback_alone_leaves_state(
    evaluation_api, evaluation_schema
):
    proposed = batch(evaluation_api, evaluation_schema)
    candidate = singleton(proposed)
    definition = CandidateDefinition.model_validate(candidate["definition"])
    with connect_local("analyzer") as first, connect_local("analyzer") as second:
        with HypotheticalSession(first) as a:
            a.create(uuid.UUID(candidate["id"]), definition)
            assert first.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 1
            with HypotheticalSession(second) as b:
                assert second.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 0
                b.create(uuid.UUID(candidate["id"]), definition)
                first.rollback()
                assert first.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 1
            assert first.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 1
        assert first.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 0
        assert second.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 0


def test_cleanup_recovers_a_real_statement_timeout(evaluation_api, evaluation_schema):
    proposed = batch(evaluation_api, evaluation_schema)
    candidate = singleton(proposed)
    with connect_local("analyzer") as connection:
        with (
            pytest.raises(psycopg.errors.QueryCanceled),
            HypotheticalSession(connection) as session,
        ):
            session.create(
                uuid.UUID(candidate["id"]),
                CandidateDefinition.model_validate(candidate["definition"]),
            )
            connection.execute("SELECT set_config('statement_timeout','30',true)")
            connection.execute(
                "SELECT pg_sleep(0.2)"
            )  # Controlled internal failure probe, not workload execution.
        assert session.cleanup_confirmed
        assert connection.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 0
        assert connection.execute("SHOW transaction_read_only").fetchone()[0] == "on"


def test_cached_sets_keep_connection_clean_and_reject_changed_settings(
    evaluation_api, evaluation_schema
):
    proposed = batch(evaluation_api, evaluation_schema)
    sources, stored = load_context(evaluation_api, proposed["id"])
    settings = evaluation_api[1]
    with (
        target_connection(settings, repeatable_read=True) as connection,
        HypotheticalSession(connection) as session,
    ):
        budget = EvaluationBudget(connection, seconds=30, statement_timeout_ms=5000)
        queries, candidates = prepare_context(
            connection,
            sources,
            stored,
            allowed_schemas=settings.analysis_schemas,
            check=budget.check,
        )
        evaluator = WorkloadEvaluator(connection, session, queries, candidates, budget)
        key = frozenset([uuid.UUID(singleton(proposed)["id"])])
        first = evaluator.evaluate(key)
        first.weighted_cost = -1
        second = evaluator.evaluate(key)
        assert second.weighted_cost >= 0 and len(evaluator.cache.values) == 2
        assert connection.execute("SELECT count(*) FROM public.hypopg()").fetchone()[0] == 0
        connection.execute("SELECT set_config('enable_seqscan','off',true)")
        with pytest.raises(DomainError) as error:
            evaluator.evaluate(key)
        assert error.value.code == "evaluation_context_changed"
        with pytest.raises(DomainError, match="must be discarded"):
            evaluator.evaluate(key)


def test_unknown_size_stays_unknown_in_actual_api(evaluation_api, evaluation_schema, admin):
    proposed = batch(evaluation_api, evaluation_schema)
    candidate = singleton(proposed)
    admin.execute("REVOKE EXECUTE ON FUNCTION public.hypopg_relation_size(oid) FROM PUBLIC")
    try:
        response = evaluation_api[0].post(
            "/api/v1/evaluations",
            json={"batch_id": proposed["id"], "candidate_sets": [[candidate["id"]]]},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "completed" and not data["capability"]["storage_available"]
        assert not data["trials"][0]["storage_complete"]
        assert data["trials"][0]["estimated_size_bytes"] is None
        assert data["trials"][0]["indexes"][0]["estimated_size_bytes"] is None
    finally:
        admin.execute("GRANT EXECUTE ON FUNCTION public.hypopg_relation_size(oid) TO PUBLIC")


def test_inaccessible_hypopg_returns_saved_unavailable_without_estimates(
    evaluation_api, evaluation_schema, admin
):
    proposed = batch(evaluation_api, evaluation_schema)
    admin.execute("REVOKE EXECUTE ON FUNCTION public.hypopg_create_index(text) FROM PUBLIC")
    try:
        response = evaluation_api[0].post("/api/v1/evaluations", json={"batch_id": proposed["id"]})
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "unavailable" and data["baseline"] is None and data["trials"] == []
        assert not data["capability"]["available"] and data["warnings"]
    finally:
        admin.execute("GRANT EXECUTE ON FUNCTION public.hypopg_create_index(text) TO PUBLIC")


def test_missing_extension_is_detected_against_real_postgres_database(monkeypatch):
    monkeypatch.setitem(ROLES, "m6_no_hypo", ("postgres", "postgres", "admin_password"))
    with connect_local("m6_no_hypo") as connection:
        with pytest.raises(HypoPGUnavailable) as error, HypotheticalSession(connection):
            pass
        assert not error.value.capability.available
        assert "not installed" in error.value.message


def test_cleanup_failure_discards_physical_connection(evaluation_api, evaluation_schema, admin):
    proposed = batch(evaluation_api, evaluation_schema)
    candidate = singleton(proposed)
    connection = connect_local("analyzer")
    try:
        with (
            pytest.raises(DomainError, match="discarded"),
            HypotheticalSession(connection) as session,
        ):
            session.create(
                uuid.UUID(candidate["id"]),
                CandidateDefinition.model_validate(candidate["definition"]),
            )
            pid = connection.execute("SELECT pg_backend_pid()").fetchone()[0]
            assert admin.execute("SELECT pg_terminate_backend(%s,2000)", (pid,)).fetchone()[0]
        assert connection.closed and not session.cleanup_confirmed
    finally:
        connection.close()


def test_saved_ddl_tampering_is_rejected_before_hypopg(evaluation_api, evaluation_schema, caplog):
    proposed = batch(evaluation_api, evaluation_schema)
    candidate = singleton(proposed)
    identifier = uuid.UUID(candidate["id"])
    engine = evaluation_api[2]
    bad = {**candidate["definition"], "ddl": "SELECT 'private-tamper-marker'; SELECT pg_sleep(10)"}
    with Session(engine) as db, db.begin():
        db.execute(
            update(IndexCandidate).where(IndexCandidate.id == identifier).values(definition=bad)
        )
    try:
        response = evaluation_api[0].post(
            "/api/v1/evaluations",
            json={"batch_id": proposed["id"], "candidate_sets": [[str(identifier)]]},
        )
        assert (
            response.status_code == 409 and response.json()["error"]["code"] == "invalid_candidate"
        )
        assert "private-tamper-marker" not in response.text + caplog.text
        history = evaluation_api[0].get(f"/api/v1/evaluations?batch_id={proposed['id']}").json()
        failed = evaluation_api[0].get(f"/api/v1/evaluations/{history[0]['id']}").json()
        assert failed["status"] == "failed" and failed["baseline"] is None and not failed["trials"]
        assert failed["cleanup_confirmed"]
    finally:
        with Session(engine) as db, db.begin():
            db.execute(
                update(IndexCandidate)
                .where(IndexCandidate.id == identifier)
                .values(definition=candidate["definition"])
            )


def test_now_existing_candidate_and_invalid_membership(evaluation_api, evaluation_schema):
    proposed = batch(evaluation_api, evaluation_schema)
    candidate = singleton(proposed)
    client = evaluation_api[0]
    assert (
        client.post(
            "/api/v1/evaluations",
            json={"batch_id": proposed["id"], "candidate_sets": [[str(uuid.uuid4())]]},
        ).status_code
        == 422
    )
    with connect_local("demo", autocommit=True) as owner:
        owner.execute(
            sql.SQL("CREATE INDEX later_user ON {}.orders(user_id)").format(
                sql.Identifier(evaluation_schema)
            )
        )
        try:
            response = client.post(
                "/api/v1/evaluations",
                json={"batch_id": proposed["id"], "candidate_sets": [[candidate["id"]]]},
            )
            assert (
                response.status_code == 409
                and response.json()["error"]["code"] == "candidate_already_exists"
            )
        finally:
            owner.execute(
                sql.SQL("DROP INDEX {}.later_user").format(sql.Identifier(evaluation_schema))
            )


def test_concurrent_runs_use_separate_backend_sessions(evaluation_api, evaluation_schema):
    proposed = batch(evaluation_api, evaluation_schema)
    body = EvaluationRequest(batch_id=proposed["id"], candidate_sets=[[singleton(proposed)["id"]]])
    _, settings, engine, _, _ = evaluation_api
    with ThreadPoolExecutor(max_workers=2) as executor:
        runs = list(executor.map(lambda _: evaluate_batch(engine, settings, body), range(2)))
    assert all(run.status == "completed" and run.cleanup_confirmed for run in runs)
    assert runs[0].context["backend_pid"] != runs[1].context["backend_pid"]
    assert runs[0].trials[0].weighted_cost == runs[1].trials[0].weighted_cost


def test_empty_candidate_batch_has_a_real_baseline(evaluation_api):
    proposed = batch(evaluation_api, "unused", query={"sql": "SELECT 1 WHERE false"})
    response = evaluation_api[0].post("/api/v1/evaluations", json={"batch_id": proposed["id"]})
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "completed" and data["trials"] == []
    assert data["baseline"]["weighted_cost"] >= 0
    expected = 0 if data["baseline"]["weighted_cost"] > 0 else None
    assert data["baseline"]["estimated_improvement_pct"] == expected
    assert data["baseline"]["estimated_size_bytes"] == 0 and data["baseline"]["storage_complete"]


def test_expired_budget_aborts_and_cleans_context(evaluation_api, evaluation_schema):
    proposed = batch(evaluation_api, evaluation_schema)
    sources, stored = load_context(evaluation_api, proposed["id"])
    settings = evaluation_api[1]
    with (
        target_connection(settings, repeatable_read=True) as connection,
        HypotheticalSession(connection) as session,
    ):
        budget = EvaluationBudget(connection, seconds=30, statement_timeout_ms=5000)
        queries, candidates = prepare_context(
            connection,
            sources,
            stored,
            allowed_schemas=settings.analysis_schemas,
            check=budget.check,
        )
        evaluator = WorkloadEvaluator(connection, session, queries, candidates, budget)
        budget.deadline = 0
        with pytest.raises(DomainError) as error:
            evaluator.evaluate()
        assert error.value.code == "evaluation_timeout"
        with pytest.raises(DomainError, match="must be discarded"):
            evaluator.evaluate()
    assert session.cleanup_confirmed
