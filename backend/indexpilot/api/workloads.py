import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from indexpilot.api.dependencies import get_engine
from indexpilot.errors import DomainError
from indexpilot.sql.validation import MAX_SQL_BYTES, split_workload
from indexpilot.workloads import service
from indexpilot.workloads.models import (
    CollectedWorkloadInput,
    ManualWorkloadInput,
    QueryInput,
    ScenarioInput,
    ScenarioView,
    SnapshotDelta,
    SnapshotSummary,
    SnapshotView,
    SQLWorkloadInput,
    WorkloadSummary,
    WorkloadView,
)

router = APIRouter(prefix="/api/v1", tags=["workloads"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]


@router.post("/workloads/manual", response_model=WorkloadView, status_code=201)
def manual(body: ManualWorkloadInput, request: Request):
    return service.create_manual(get_engine(request), request.app.state.settings, body)


@router.post("/workloads/sql", response_model=WorkloadView, status_code=201)
def sql_text(body: SQLWorkloadInput, request: Request):
    queries = [QueryInput(sql=sql, frequency=body.frequency) for sql in split_workload(body.sql)]
    return manual(ManualWorkloadInput(name=body.name, queries=queries), request)


@router.post("/workloads/upload", response_model=WorkloadView, status_code=201)
async def upload(
    request: Request,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(min_length=1, max_length=120)] = "Uploaded workload",
    frequency: Annotated[float, Form(gt=0, le=1_000_000_000, allow_inf_nan=False)] = 1,
):
    try:
        if not file.filename or not file.filename.lower().endswith(".sql"):
            raise DomainError("invalid_file", "Upload a UTF-8 .sql file.")
        content = await file.read(MAX_SQL_BYTES + 1)
        if len(content) > MAX_SQL_BYTES:
            raise DomainError("invalid_sql_size", "SQL files may contain at most 65536 bytes.")
        try:
            sql = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise DomainError("invalid_encoding", "SQL files must use UTF-8 encoding.") from None
        queries = [
            QueryInput(sql=statement, frequency=frequency) for statement in split_workload(sql)
        ]
        return await run_in_threadpool(
            manual,
            ManualWorkloadInput(name=name, queries=queries),
            request,
        )
    finally:
        await file.close()


@router.post("/workloads/collected", response_model=WorkloadView, status_code=201)
def collected(body: CollectedWorkloadInput, request: Request):
    return service.create_collected(get_engine(request), request.app.state.settings, body.name)


@router.get("/workloads", response_model=list[WorkloadSummary])
def workloads(request: Request, limit: Limit = 50, offset: Offset = 0):
    return service.list_workloads(get_engine(request), limit=limit, offset=offset)


@router.get("/workloads/{workload_id}", response_model=WorkloadView)
def workload(workload_id: uuid.UUID, request: Request, limit: Limit = 100, offset: Offset = 0):
    return service.get_workload(get_engine(request), workload_id, limit=limit, offset=offset)


@router.post("/query-patterns/{pattern_id}/scenarios", response_model=ScenarioView, status_code=201)
def scenario(pattern_id: uuid.UUID, body: ScenarioInput, request: Request):
    return service.add_scenario(
        get_engine(request), pattern_id, body, settings=request.app.state.settings
    )


@router.post("/workloads/{workload_id}/snapshots", response_model=SnapshotView, status_code=201)
def take_snapshot(workload_id: uuid.UUID, request: Request):
    return service.take_snapshot(get_engine(request), request.app.state.settings, workload_id)


@router.get("/workloads/{workload_id}/snapshots", response_model=list[SnapshotSummary])
def snapshots(workload_id: uuid.UUID, request: Request, limit: Limit = 50, offset: Offset = 0):
    return service.list_snapshots(get_engine(request), workload_id, limit=limit, offset=offset)


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotView)
def snapshot(snapshot_id: uuid.UUID, request: Request):
    return service.get_snapshot(get_engine(request), snapshot_id)


@router.get("/snapshots/{snapshot_id}/delta", response_model=SnapshotDelta)
def delta(snapshot_id: uuid.UUID, request: Request, previous_id: uuid.UUID | None = None):
    return service.get_delta(get_engine(request), snapshot_id, previous_id)
