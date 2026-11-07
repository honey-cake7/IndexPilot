import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_serializer, model_validator

Frequency = Annotated[float, Field(gt=0, le=1_000_000_000, allow_inf_nan=False)]
Counter = Annotated[int, Field(ge=0)]
Millis = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Parameter(InputModel):
    type: Literal["int8", "numeric", "text", "date", "timestamp", "timestamptz", "bool"]
    value: str | int | float | bool | None

    @model_validator(mode="after")
    def bound_value(self):
        if isinstance(self.value, str) and len(self.value) > 4096:
            raise ValueError("Parameter value is too long")
        return self


class QueryInput(InputModel):
    sql: str = Field(min_length=1, max_length=65_536)
    frequency: Frequency = 1
    parameters: dict[Annotated[int, Field(ge=1, le=100)], Parameter] = Field(default_factory=dict)


class ManualWorkloadInput(InputModel):
    name: str = Field(default="Manual workload", min_length=1, max_length=120)
    queries: list[QueryInput] = Field(min_length=1, max_length=100)


class SQLWorkloadInput(InputModel):
    name: str = Field(default="SQL workload", min_length=1, max_length=120)
    sql: str = Field(min_length=1, max_length=65_536)
    frequency: Frequency = 1


class CollectedWorkloadInput(InputModel):
    name: str = Field(default="Collected workload", min_length=1, max_length=120)


class ScenarioInput(InputModel):
    frequency: Frequency = 1
    parameters: dict[Annotated[int, Field(ge=1, le=100)], Parameter]


class ScenarioView(BaseModel):
    id: uuid.UUID
    sql: str
    parameters: dict[str, JsonValue]
    representative_sql: str | None
    frequency: float
    missing_parameters: list[int]
    validation: Literal["syntax_only"] = "syntax_only"


class PatternView(BaseModel):
    id: uuid.UUID
    identity: str
    fingerprint: str
    normalized_sql: str
    server_queryid: int | None
    server_userid: int | None
    server_dbid: int | None
    server_toplevel: bool | None
    scenarios: list[ScenarioView]

    @field_serializer("server_queryid", when_used="json")
    def serialize_queryid(self, value: int | None) -> str | None:
        return str(value) if value is not None else None


class WorkloadView(BaseModel):
    id: uuid.UUID
    name: str
    source: Literal["manual", "pg_stat_statements"]
    created_at: datetime
    patterns: list[PatternView]
    pattern_total: int
    pattern_offset: int
    warnings: list[str]


class WorkloadSummary(BaseModel):
    id: uuid.UUID
    name: str
    source: str
    created_at: datetime


class StatementStats(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    identity: str
    query: str
    queryid: int
    userid: int
    dbid: int
    toplevel: bool
    calls: Counter
    total_exec_ms: Millis
    mean_exec_ms: Millis
    rows: Counter
    buffers: dict[str, Counter]
    stats_since: datetime

    @field_serializer("queryid", when_used="json")
    def serialize_queryid(self, value: int) -> str:
        # Preserve signed 64-bit identifiers for JavaScript clients.
        return str(value)


class SnapshotData(BaseModel):
    started_at: datetime
    observed_at: datetime
    server_started_at: datetime
    stats_reset: datetime
    dealloc: Counter
    dbid: int
    extension_version: str
    consistent: bool
    truncated: bool
    skipped_statements: Counter
    entries: list[StatementStats]
    warnings: list[str]


class SnapshotView(SnapshotData):
    id: uuid.UUID
    workload_id: uuid.UUID


class SnapshotSummary(BaseModel):
    id: uuid.UUID
    workload_id: uuid.UUID
    started_at: datetime
    observed_at: datetime
    consistent: bool
    truncated: bool


class DeltaEntry(BaseModel):
    identity: str
    usable: bool
    reason: str | None = None
    calls: int | None = None
    total_exec_ms: float | None = None
    mean_exec_ms: float | None = None
    rows: int | None = None
    buffers: dict[str, int] | None = None


class SnapshotDelta(BaseModel):
    previous_id: uuid.UUID | None = None
    current_id: uuid.UUID
    interval_seconds: float | None = None
    entries: list[DeltaEntry]
    warnings: list[str]
