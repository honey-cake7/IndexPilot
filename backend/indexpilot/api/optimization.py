import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from indexpilot.api.dependencies import get_engine
from indexpilot.optimizer.models import (
    OptimizationRequest,
    OptimizationRunView,
    OptimizationSummary,
)
from indexpilot.optimizer.persistence import get_optimization, list_optimizations
from indexpilot.optimizer.service import optimize_batch

router = APIRouter(prefix="/api/v1/optimizations", tags=["workload optimization"])


@router.post("", response_model=OptimizationRunView, status_code=201)
def optimize(body: OptimizationRequest, request: Request):
    return optimize_batch(get_engine(request), request.app.state.settings, body)


@router.get("", response_model=list[OptimizationSummary])
def optimizations(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
):
    return list_optimizations(get_engine(request), limit=limit, offset=offset)


@router.get("/{optimization_id}", response_model=OptimizationRunView)
def optimization(optimization_id: uuid.UUID, request: Request):
    return get_optimization(get_engine(request), optimization_id)
