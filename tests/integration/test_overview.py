import pytest
from fastapi.testclient import TestClient
from indexpilot.main import create_app

from tests.integration.test_benchmarks import queued
from tests.integration.test_hypopg_evaluation import evaluation_api as evaluation_api
from tests.integration.test_hypopg_evaluation import evaluation_schema as evaluation_schema

pytestmark = pytest.mark.integration


def test_dashboard_totals_include_new_records_and_job_states(evaluation_api):
    client = evaluation_api[0]
    before = client.get("/api/v1/overview").json()
    job = queued(evaluation_api)
    after_response = client.get("/api/v1/overview")
    assert after_response.status_code == 200
    after = after_response.json()
    assert after["plan_count"] == before["plan_count"] + 1
    assert after["candidate_count"] > before["candidate_count"]
    assert after["optimization_count"] == before["optimization_count"] + 1
    assert after["recommendation_count"] == before["recommendation_count"] + 1
    assert after["benchmark_count"] == before["benchmark_count"] + 1
    assert after["completed_benchmark_count"] == before["completed_benchmark_count"]
    assert after["active_benchmark_count"] == before["active_benchmark_count"] + 1
    assert client.post(f"/api/v1/benchmarks/{job.id}/cancel").status_code == 200
    final = client.get("/api/v1/overview").json()
    assert final["active_benchmark_count"] == before["active_benchmark_count"]
    assert final["benchmark_count"] == after["benchmark_count"]
    # A list page is bounded; the aggregate remains the full database count.
    assert len(client.get("/api/v1/plans?limit=1").json()) == 1
    assert final["plan_count"] >= after["plan_count"]


def test_overview_failure_uses_safe_database_envelope(tmp_path):
    from indexpilot.config import Settings

    (tmp_path / "meta_password").write_text("deliberately-wrong-overview-password")
    with TestClient(create_app(Settings(secret_dir=tmp_path))) as client:
        response = client.get("/api/v1/overview")
    assert response.status_code == 503
    assert "error" in response.json()
    assert "deliberately-wrong-overview-password" not in response.text
