import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from indexpilot.plans.models import PlanDocument
from indexpilot.sql.models import SQLAnalysis


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_id: uuid.UUID
    candidate_sets: list[Annotated[list[uuid.UUID], Field(min_length=1, max_length=32)]] | None = (
        Field(default=None, min_length=1, max_length=64)
    )

    @model_validator(mode="after")
    def unique_sets(self):
        if self.candidate_sets is not None:
            keys = []
            for group in self.candidate_sets:
                if len(set(group)) != len(group):
                    raise ValueError("Candidate IDs within a set must be distinct")
                keys.append(frozenset(group))
            if len(set(keys)) != len(keys):
                raise ValueError("Index sets must be distinct regardless of order")
        return self


class HypoPGCapability(BaseModel):
    available: bool
    schema_name: str | None = None
    version: str | None = None
    storage_available: bool = False
    warning: str | None = None


class QueryEstimate(BaseModel):
    source_plan_id: uuid.UUID
    frequency: float
    plan: PlanDocument
    raw_explain: list[dict]
    used_candidate_ids: list[uuid.UUID]
    baseline_cost: float | None = None
    estimated_improvement_pct: float | None = None
    regression: bool | None = None


class IndexEstimate(BaseModel):
    candidate_id: uuid.UUID
    hypothetical_oid: int
    hypothetical_name: str
    estimated_size_bytes: int | None


class SetEstimate(BaseModel):
    candidate_ids: list[uuid.UUID]
    indexes: list[IndexEstimate]
    queries: list[QueryEstimate]
    weighted_cost: float | None
    baseline_weighted_cost: float | None = None
    estimated_improvement_pct: float | None = None
    estimated_size_bytes: int | None
    storage_complete: bool
    warnings: list[str]
    cost_unit: Literal["planner_cost"] = "planner_cost"
    execution_measured: Literal[False] = False


class EvaluationQueryView(BaseModel):
    source_plan_id: uuid.UUID
    frequency: float
    analysis: SQLAnalysis


class EvaluationRunView(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    created_at: datetime
    status: Literal["completed", "unavailable", "failed"]
    capability: HypoPGCapability
    requested_sets: list[list[uuid.UUID]]
    context: dict
    queries: list[EvaluationQueryView]
    baseline: SetEstimate | None
    trials: list[SetEstimate]
    warnings: list[str]
    error_code: str | None
    cleanup_confirmed: bool


class EvaluationSummary(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    created_at: datetime
    status: str
    cleanup_confirmed: bool
