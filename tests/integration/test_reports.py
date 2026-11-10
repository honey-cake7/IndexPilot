import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from indexpilot.benchmarks.runner import run_next
from indexpilot.main import create_app
from indexpilot.metadata.models import BenchmarkJob, RecommendationSet, SavedReport
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from tests.integration.test_benchmarks import queued
from tests.integration.test_hypopg_evaluation import batch
from tests.integration.test_hypopg_evaluation import evaluation_api as evaluation_api
from tests.integration.test_hypopg_evaluation import evaluation_schema as evaluation_schema
from tests.integration.test_optimizer import post
from tests.integration.test_recommendations import optimization, recommend

pytestmark = pytest.mark.integration


def source(api, schema):
    opt = optimization(api, schema)
    return recommend(api, opt).json(), opt


def create(api, rec, **options):
    response = api[0].post("/api/v1/reports", json={"recommendation_id": rec["id"], **options})
    assert response.status_code == 201, response.text
    return response.json()


def test_report_freezes_costs_reasons_options_and_survives_source_change_restart(
    evaluation_api, evaluation_schema
):
    rec, opt = source(evaluation_api, evaluation_schema)
    with Session(evaluation_api[2]) as db, db.begin():
        row = db.get(RecommendationSet, uuid.UUID(rec["id"]))
        row.provenance = {
            **row.provenance,
            "password": "not-for-export",
            "evaluation_context": {
                **row.provenance["evaluation_context"],
                "password": "not-for-export",
                "dsn": "not-for-export",
            },
        }
    report = create(evaluation_api, rec, title="Historical decision")
    assert report["format_version"] == "indexpilot-report-v1"
    assert report["summary"] == rec["summary"] and report["settings"] == rec["options"]
    assert report["search_trials"] == opt["result"]["trials"]
    assert len(report["candidates"]) >= len(report["indexes"])
    assert all(c["reason"] for c in report["candidates"])
    assert report["missing_evidence"] and not report["benchmarks"]
    original = evaluation_api[0].get(f"/api/v1/reports/{report['id']}/download.json")
    assert original.json() == report
    with Session(evaluation_api[2]) as db, db.begin():
        row = db.get(RecommendationSet, uuid.UUID(rec["id"]))
        row.summary = {**row.summary, "message": "Changed after report creation"}
        row.provenance = {**row.provenance, "password": "not-for-export"}
    with TestClient(create_app(evaluation_api[1])) as restarted:
        again = restarted.get(f"/api/v1/reports/{report['id']}/download.json")
        assert again.content == original.content
        assert restarted.get(f"/api/v1/reports/{report['id']}").json() == report
    assert b"not-for-export" not in original.content


def test_parameter_policy_omits_bound_values_but_can_explicitly_include_them(
    evaluation_api, evaluation_schema
):
    proposed = batch(
        evaluation_api,
        evaluation_schema,
        query={
            "sql": f"SELECT id FROM {evaluation_schema}.orders WHERE user_id=$1",
            "parameters": {"1": {"type": "int8", "value": 987654321}},
            "frequency": 7,
        },
    )
    rec = recommend(evaluation_api, post(evaluation_api, proposed["id"]).json()).json()
    omitted = create(evaluation_api, rec)
    assert "$1" in omitted["queries"][0]["original_sql"]
    assert omitted["queries"][0]["representative_sql"] is None
    assert "987654321" not in str(omitted)
    included = create(evaluation_api, rec, include_representative_sql=True)
    assert "987654321" in included["queries"][0]["representative_sql"]
    no_sql = create(evaluation_api, rec, include_original_sql=False)
    assert all(
        q["original_sql"] is None and q["representative_sql"] is None for q in no_sql["queries"]
    )
    assert all(i["deployment_sql"] is None for i in no_sql["indexes"])


def test_report_export_safe_filename_markdown_html_and_unknown_ids(
    evaluation_api, evaluation_schema
):
    rec, _ = source(evaluation_api, evaluation_schema)
    report = create(evaluation_api, rec, title="../../<img src=x onerror=alert(1)> [bad](link)")
    client = evaluation_api[0]
    md = client.get(f"/api/v1/reports/{report['id']}/download.md")
    assert md.status_code == 200 and "&lt;img" in md.text
    assert "<img" not in md.text
    assert (
        md.headers["content-disposition"]
        == f'attachment; filename="indexpilot-report-{report["id"]}.md"'
    )
    assert md.headers["x-content-type-options"] == "nosniff"
    assert "planner_cost" in md.text and "bytes" in md.text and "No benchmark" in md.text
    for query in report["queries"]:
        assert query["original_sql"] in md.text
    assert client.get(f"/api/v1/reports/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/v1/reports/%0d%0aevil/download.json").status_code == 422


def test_terminal_benchmark_scope_and_no_partial_report_on_active_job(
    evaluation_api, evaluation_schema
):
    job = queued(evaluation_api)
    rec = {"id": str(job.recommendation_id)}
    client = evaluation_api[0]
    active = client.post(
        "/api/v1/reports", json={"recommendation_id": rec["id"], "benchmark_ids": [str(job.id)]}
    )
    assert active.status_code == 409 and active.json()["error"]["code"] == "report_benchmark_active"
    assert (
        client.get("/api/v1/reports", params={"recommendation_id": rec["id"]}).json()["total"] == 0
    )
    other, _ = source(evaluation_api, evaluation_schema)
    mismatch = client.post(
        "/api/v1/reports", json={"recommendation_id": other["id"], "benchmark_ids": [str(job.id)]}
    )
    assert mismatch.status_code == 422
    assert client.post(f"/api/v1/benchmarks/{job.id}/cancel").status_code == 200
    report = create(evaluation_api, rec, benchmark_ids=[str(job.id)])
    assert report["benchmarks"][0]["status"] == "cancelled"
    assert not report["benchmarks"][0]["complete_comparison"]
    assert report["benchmarks"][0]["comparisons"] == []
    assert any("cancelled" in missing for missing in report["missing_evidence"])


def test_real_measured_report_matches_pgbench_and_remains_frozen(evaluation_api):
    job = queued(evaluation_api)
    assert run_next(evaluation_api[2], evaluation_api[1]) == job.id
    assert evaluation_api[0].get(f"/api/v1/benchmarks/{job.id}").json()["status"] == "completed"
    report = create(evaluation_api, {"id": str(job.recommendation_id)}, benchmark_ids=[str(job.id)])
    measurements = evaluation_api[0].get(f"/api/v1/benchmarks/{job.id}/measurements").json()
    assert report["benchmarks"][0]["complete_comparison"]
    assert len(report["benchmarks"][0]["measurements"]) == len(measurements) == 15
    assert (
        report["benchmarks"][0]["measurements"][0]["metrics"]["mean_ms"]
        == measurements[0]["metrics"]["mean_ms"]
    )
    assert report["benchmarks"][0]["comparisons"]
    with Session(evaluation_api[2]) as db, db.begin():
        db.execute(update(BenchmarkJob).where(BenchmarkJob.id == job.id).values(result=None))
    assert evaluation_api[0].get(f"/api/v1/reports/{report['id']}").json() == report


def test_large_history_paginates_filters_literal_search_and_dates(
    evaluation_api, evaluation_schema
):
    rec, _ = source(evaluation_api, evaluation_schema)
    report = create(evaluation_api, rec)
    prefix = "history_" + uuid.uuid4().hex
    timestamp = datetime.now(UTC)
    with Session(evaluation_api[2]) as db, db.begin():
        for i in range(105):
            identifier = uuid.uuid4()
            title = f"{prefix}_%_{i}"
            doc = {
                **report,
                "id": str(identifier),
                "title": title,
                "created_at": timestamp.isoformat(),
            }
            db.add(
                SavedReport(
                    id=identifier,
                    recommendation_id=uuid.UUID(rec["id"]),
                    title=title,
                    created_at=timestamp,
                    format_version=report["format_version"],
                    document=doc,
                )
            )
    client = evaluation_api[0]
    first = client.get(
        "/api/v1/history", params={"kind": "reports", "q": prefix, "limit": 100}
    ).json()
    last = client.get(
        "/api/v1/history", params={"kind": "reports", "q": prefix, "limit": 100, "offset": 100}
    ).json()
    assert (
        first["total"] == last["total"] == 105
        and len(first["items"]) == 100
        and len(last["items"]) == 5
    )
    assert len({item["id"] for item in first["items"] + last["items"]}) == 105
    # This bait would match unescaped _%_ wildcards, but not the literal search.
    with Session(evaluation_api[2]) as db, db.begin():
        bait_id = uuid.uuid4()
        bait_title = prefix + "XAYbait"
        db.add(
            SavedReport(
                id=bait_id,
                recommendation_id=uuid.UUID(rec["id"]),
                title=bait_title,
                created_at=timestamp,
                format_version=report["format_version"],
                document={**report, "id": str(bait_id), "title": bait_title},
            )
        )
    literal = client.get("/api/v1/reports", params={"q": prefix + "_%_", "limit": 100}).json()
    assert literal["total"] == 105
    empty = client.get(
        "/api/v1/history", params={"q": prefix, "created_from": "2100-01-01T00:00:00Z"}
    ).json()
    assert empty["total"] == 0
    invalid = client.get(
        "/api/v1/history?created_from=2027-01-01T00:00:00Z&created_to=2026-01-01T00:00:00Z"
    )
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "invalid_history_range"
    assert client.get("/api/v1/history", params={"q": "' OR 1=1 --"}).json()["total"] == 0
    with Session(evaluation_api[2]) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(SavedReport)
                .where(SavedReport.recommendation_id == uuid.UUID(rec["id"]))
            )
            == 107
        )
