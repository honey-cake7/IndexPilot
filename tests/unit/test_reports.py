import uuid

import pytest
from fastapi.testclient import TestClient
from indexpilot.main import create_app
from indexpilot.reports.models import ReportRequest
from indexpilot.reports.render import block, number, text
from pydantic import ValidationError


@pytest.mark.parametrize(
    "changes",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "bad\r\nInjected: yes"},
        {"title": "x\x00"},
        {"title": "x" * 121},
        {"include_original_sql": "false"},
        {"include_representative_sql": 1},
        {"include_original_sql": False, "include_representative_sql": True},
        {"benchmark_ids": [uuid.UUID(int=1)] * 2},
        {"benchmark_ids": [uuid.uuid4() for _ in range(6)]},
        {"unknown_option": True},
    ],
)
def test_report_rejects_invalid_policy_title_or_selection(changes):
    with pytest.raises(ValidationError):
        ReportRequest(recommendation_id=uuid.uuid4(), **changes)


def test_default_report_policy_is_explicit_and_title_trimmed():
    request = ReportRequest(recommendation_id=uuid.uuid4(), title="  Useful report  ")
    assert request.title == "Useful report"
    assert request.include_original_sql and not request.include_representative_sql


@pytest.mark.parametrize(
    "sql", ["SELECT 1;", "SELECT $$```\n<script>x</script>\n```$$;", "SELECT $$``````$$;"]
)
def test_markdown_code_fence_cannot_be_closed_by_query(sql):
    rendered = block(sql, "sql")
    opening, _, closing = rendered.partition("\n")
    fence = opening.removesuffix("sql")
    assert len(fence) >= 3 and fence not in sql
    assert closing.endswith("\n" + fence)
    assert sql in rendered


def test_markdown_prose_escapes_html_and_link_injection():
    value = text("<img src=x onerror=alert(1)> [click](javascript:evil)\n# title")
    assert "<img" not in value and "&lt;img" in value
    assert r"\[click\]" in value and r"\# title" in value
    assert number(None) == "Unknown"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/reports/not-a-uuid/download.md",
        "/api/v1/history?kind=invalid",
        "/api/v1/history?limit=101",
        "/api/v1/history?created_from=2026-11-10T00:00:00",
        "/api/v1/reports?offset=-1",
        "/api/v1/history?q=" + "x" * 121,
    ],
)
def test_invalid_report_history_request_rejected_before_db_access(path):
    with TestClient(create_app()) as client:
        response = client.get(path)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
