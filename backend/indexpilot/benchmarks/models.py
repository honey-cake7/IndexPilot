import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BenchmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    recommendation_id: uuid.UUID
    confirm_disposable_benchmark: Literal[True]
    orders: Annotated[int, Field(strict=True, ge=1000, le=100000)] = 10000
    seed: Annotated[int, Field(strict=True, ge=0, le=2147483647)] = 42
    repetitions: Annotated[int, Field(strict=True, ge=1, le=5)] = 3
    clients: Annotated[int, Field(strict=True, ge=1, le=4)] = 1
    transactions_per_client: Annotated[int, Field(strict=True, ge=5, le=10000)] = 200
    read_warmup_per_client: Annotated[int, Field(strict=True, ge=0, le=1000)] = 20
    timeout_seconds: Annotated[int, Field(strict=True, ge=10, le=600)] = 300
    regression_threshold_pct: Annotated[float, Field(ge=0, le=1000)] = 10

    @field_validator("confirm_disposable_benchmark", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError(
                "Explicit boolean true is required for disposable physical benchmarking"
            )
        return value


class BenchmarkView(BaseModel):
    id: uuid.UUID
    recommendation_id: uuid.UUID
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    request: dict
    manifest: dict
    result: dict | None
    error_code: str | None
    cleanup_confirmed: bool
    cancel_requested: bool
    created_at: str
    started_at: str | None
    finished_at: str | None


class MeasurementView(BaseModel):
    id: uuid.UUID
    repetition: int
    arm: str
    phase: str
    metrics: dict
    conditions: dict
