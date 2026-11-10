import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import String, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from indexpilot.api.dependencies import get_engine
from indexpilot.errors import DomainError
from indexpilot.metadata.models import (
    BenchmarkJob,
    CandidateBatch,
    OptimizationRun,
    PlanAnalysis,
    RecommendationSet,
    SavedReport,
    Workload,
)

Kind = Literal[
    "workloads", "plans", "candidates", "optimizations", "recommendations", "benchmarks", "reports"
]
router = APIRouter(prefix="/api/v1/history", tags=["saved history"])


class HistoryItem(BaseModel):
    id: uuid.UUID
    kind: Kind
    title: str
    created_at: datetime
    status: str | None


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    limit: int
    offset: int


@router.get("", response_model=HistoryPage)
def history(
    request: Request,
    kind: Kind | None = None,
    q: Annotated[str, Query(max_length=120)] = "",
    created_from: Annotated[AwareDatetime | None, Query()] = None,
    created_to: Annotated[AwareDatetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
):
    if created_from and created_to and created_from > created_to:
        raise DomainError("invalid_history_range", "Saved-from must be earlier than saved-to.", 422)
    sources = [
        ("workloads", Workload, Workload.created_at, Workload.name, literal(None, String)),
        (
            "plans",
            PlanAnalysis,
            PlanAnalysis.captured_at,
            PlanAnalysis.root_node_type,
            literal(None, String),
        ),
        (
            "candidates",
            CandidateBatch,
            CandidateBatch.created_at,
            literal("Candidate batch"),
            literal(None, String),
        ),
        (
            "optimizations",
            OptimizationRun,
            OptimizationRun.created_at,
            literal("Optimizer run"),
            literal(None, String),
        ),
        (
            "recommendations",
            RecommendationSet,
            RecommendationSet.created_at,
            literal("Recommendation"),
            literal(None, String),
        ),
        (
            "benchmarks",
            BenchmarkJob,
            BenchmarkJob.created_at,
            literal("Physical benchmark"),
            BenchmarkJob.status,
        ),
        ("reports", SavedReport, SavedReport.created_at, SavedReport.title, literal(None, String)),
    ]
    combined = union_all(
        *[
            select(
                model.id.label("id"),
                literal(name).label("kind"),
                title.label("title"),
                timestamp.label("created_at"),
                status.label("status"),
            )
            for name, model, timestamp, title, status in sources
            if kind is None or kind == name
        ]
    ).subquery()
    statement = select(combined)
    if q:
        statement = statement.where(
            or_(
                combined.c.title.icontains(q, autoescape=True),
                cast(combined.c.id, String).icontains(q, autoescape=True),
            )
        )
    if created_from:
        statement = statement.where(combined.c.created_at >= created_from)
    if created_to:
        statement = statement.where(combined.c.created_at <= created_to)
    with (
        get_engine(request)
        .connect()
        .execution_options(isolation_level="REPEATABLE READ") as connection,
        connection.begin(),
        Session(connection) as db,
    ):
        total = db.scalar(select(func.count()).select_from(statement.subquery()))
        rows = db.execute(
            statement.order_by(combined.c.created_at.desc(), combined.c.kind, combined.c.id)
            .limit(limit)
            .offset(offset)
        ).mappings()
        return HistoryPage(
            items=[HistoryItem(**row) for row in rows], total=total, limit=limit, offset=offset
        )
