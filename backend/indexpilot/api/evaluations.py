import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from indexpilot.api.dependencies import get_engine
from indexpilot.evaluation.models import EvaluationRequest, EvaluationRunView, EvaluationSummary
from indexpilot.evaluation.persistence import get_run, list_runs
from indexpilot.evaluation.service import evaluate_batch

router = APIRouter(prefix="/api/v1/evaluations", tags=["hypothetical evaluation"])


@router.post("", response_model=EvaluationRunView, status_code=201)
def evaluate(body: EvaluationRequest, request: Request):
    return evaluate_batch(get_engine(request), request.app.state.settings, body)


@router.get("", response_model=list[EvaluationSummary])
def evaluations(
    request: Request,
    batch_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
):
    return list_runs(get_engine(request), batch_id=batch_id, limit=limit, offset=offset)


@router.get("/{evaluation_id}", response_model=EvaluationRunView)
def evaluation(evaluation_id: uuid.UUID, request: Request):
    return get_run(get_engine(request), evaluation_id)
