import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from indexpilot.api.dependencies import get_engine
from indexpilot.candidates import service
from indexpilot.candidates.models import CandidateBatchSummary, CandidateBatchView, CandidateRequest

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])


@router.post("", response_model=CandidateBatchView, status_code=201)
def generate(body: CandidateRequest, request: Request):
    return service.create_batch(get_engine(request), request.app.state.settings, body)


@router.get("", response_model=list[CandidateBatchSummary])
def batches(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
):
    return service.list_batches(get_engine(request), limit=limit, offset=offset)


@router.get("/{batch_id}", response_model=CandidateBatchView)
def batch(batch_id: uuid.UUID, request: Request):
    return service.get_batch(get_engine(request), batch_id)
