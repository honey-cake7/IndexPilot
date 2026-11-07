import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from indexpilot.api.dependencies import get_engine
from indexpilot.plans import service
from indexpilot.plans.models import PlanRecord, PlanSummary
from indexpilot.workloads.models import QueryInput

router = APIRouter(prefix="/api/v1", tags=["plans"])


@router.post("/plans", response_model=PlanRecord, status_code=201)
def analyze(body: QueryInput, request: Request):
    return service.analyze_query(get_engine(request), request.app.state.settings, body)


@router.post("/query-scenarios/{scenario_id}/plan", response_model=PlanRecord, status_code=201)
def scenario_plan(scenario_id: uuid.UUID, request: Request):
    return service.analyze_scenario(get_engine(request), request.app.state.settings, scenario_id)


@router.get("/plans", response_model=list[PlanSummary])
def plans(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
):
    return service.list_plans(get_engine(request), limit=limit, offset=offset)


@router.get("/plans/{plan_id}", response_model=PlanRecord)
def plan(plan_id: uuid.UUID, request: Request):
    return service.get_plan(get_engine(request), plan_id)
