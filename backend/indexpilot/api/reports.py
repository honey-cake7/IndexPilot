import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from indexpilot.api.dependencies import get_engine
from indexpilot.reports.models import ReportDocument, ReportPage, ReportRequest
from indexpilot.reports.render import markdown
from indexpilot.reports.service import create_report, get_report, list_reports

router = APIRouter(prefix="/api/v1/reports", tags=["saved reports"])


@router.post("", response_model=ReportDocument, status_code=201)
def create(body: ReportRequest, request: Request):
    return create_report(get_engine(request), body)


@router.get("", response_model=ReportPage)
def history(
    request: Request,
    recommendation_id: uuid.UUID | None = None,
    q: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
):
    return list_reports(
        get_engine(request), recommendation_id=recommendation_id, q=q, limit=limit, offset=offset
    )


@router.get("/{report_id}", response_model=ReportDocument)
def report(report_id: uuid.UUID, request: Request):
    return get_report(get_engine(request), report_id)


def artifact(identifier, content, extension, media_type):
    # Only a parsed UUID reaches this filename; titles/paths never enter headers.
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="indexpilot-report-{identifier}.{extension}"'
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/{report_id}/download.json", response_class=Response)
def download_json(report_id: uuid.UUID, request: Request):
    data = get_report(get_engine(request), report_id)
    return artifact(report_id, data.model_dump_json(indent=2), "json", "application/json")


@router.get("/{report_id}/download.md", response_class=Response)
def download_markdown(report_id: uuid.UUID, request: Request):
    return artifact(
        report_id, markdown(get_report(get_engine(request), report_id)), "md", "text/markdown"
    )
