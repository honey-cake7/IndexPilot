import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from indexpilot.api.dependencies import get_engine
from indexpilot.benchmarks.jobs import (
    cancel,
    enqueue,
    get_job,
    list_jobs,
    list_measurements,
    samples,
)
from indexpilot.benchmarks.models import BenchmarkRequest, BenchmarkView, MeasurementView

router = APIRouter(prefix="/api/v1/benchmarks", tags=["isolated benchmarks"])


@router.post("", response_model=BenchmarkView, status_code=202)
def create(body: BenchmarkRequest, request: Request):
    return enqueue(get_engine(request), body)


@router.get("", response_model=list[BenchmarkView])
def history(
    request: Request,
    recommendation_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
):
    return list_jobs(
        get_engine(request), recommendation_id=recommendation_id, limit=limit, offset=offset
    )


@router.get("/{job_id}", response_model=BenchmarkView)
def job(job_id: uuid.UUID, request: Request):
    return get_job(get_engine(request), job_id)


@router.post("/{job_id}/cancel", response_model=BenchmarkView)
def stop(job_id: uuid.UUID, request: Request):
    return cancel(get_engine(request), job_id)


@router.get("/{job_id}/measurements", response_model=list[MeasurementView])
def measurements(job_id: uuid.UUID, request: Request):
    return list_measurements(get_engine(request), job_id)


@router.get("/measurements/{measurement_id}/samples")
def transaction_samples(
    measurement_id: uuid.UUID,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
):
    return samples(get_engine(request), measurement_id, limit=limit, offset=offset)
