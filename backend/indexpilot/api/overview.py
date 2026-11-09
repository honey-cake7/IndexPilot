from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from indexpilot.api.dependencies import get_engine
from indexpilot.metadata.models import (
    BenchmarkJob,
    IndexCandidate,
    OptimizationRun,
    PlanAnalysis,
    RecommendationSet,
    Workload,
)

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


class OverviewStats(BaseModel):
    workload_count: int
    plan_count: int
    candidate_count: int
    optimization_count: int
    recommendation_count: int
    benchmark_count: int
    completed_benchmark_count: int
    active_benchmark_count: int


def count(model, *conditions):
    return select(func.count()).select_from(model).where(*conditions).scalar_subquery()


@router.get("/overview", response_model=OverviewStats)
def overview(request: Request):
    # One SQL statement gives counts from one MVCC statement snapshot; list-page lengths
    # are never presented as database totals.
    with Session(get_engine(request)) as db:
        row = (
            db.execute(
                select(
                    count(Workload).label("workload_count"),
                    count(PlanAnalysis).label("plan_count"),
                    count(IndexCandidate, IndexCandidate.status == "proposed").label(
                        "candidate_count"
                    ),
                    count(OptimizationRun).label("optimization_count"),
                    count(RecommendationSet).label("recommendation_count"),
                    count(BenchmarkJob).label("benchmark_count"),
                    count(
                        BenchmarkJob,
                        BenchmarkJob.status == "completed",
                        BenchmarkJob.cleanup_confirmed.is_(True),
                    ).label("completed_benchmark_count"),
                    count(BenchmarkJob, BenchmarkJob.status.in_(["queued", "running"])).label(
                        "active_benchmark_count"
                    ),
                )
            )
            .mappings()
            .one()
        )
        return OverviewStats(**row)
