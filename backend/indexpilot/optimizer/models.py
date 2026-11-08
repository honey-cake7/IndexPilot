import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from indexpilot.evaluation.models import SetEstimate

Weight = Annotated[float, Field(ge=0, le=1e9, allow_inf_nan=False)]


class OptimizationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    storage_budget_bytes: Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]
    max_selected_indexes: Annotated[int, Field(strict=True, ge=0, le=32)] = 8
    max_evaluations: Annotated[int, Field(strict=True, ge=2, le=1024)] = 128
    max_query_regression_pct: Annotated[float, Field(ge=0, le=1e6)] | None = None
    write_penalty_cost_per_mib: Annotated[float, Field(ge=0, le=1e12)] = 0
    write_weights: dict[uuid.UUID, Weight] = Field(default_factory=dict, max_length=32)
    frequency_basis: str = Field(default="user_supplied_scenario", min_length=1, max_length=100)


class OptimizationRequest(OptimizationOptions):
    batch_id: uuid.UUID


class SearchCandidate(BaseModel):
    id: uuid.UUID
    signature: str = Field(min_length=1, max_length=64)


class ObjectiveScore(BaseModel):
    read_cost: float | None
    storage_bytes: int | None
    write_penalty: float | None
    objective: float | None
    feasible: bool
    reason: str | None = None


class QueryChange(BaseModel):
    source_plan_id: uuid.UUID
    frequency: float
    baseline_cost: float | None
    cost: float | None
    absolute_change: float | None
    estimated_improvement_pct: float | None
    regression: bool | None


class Trial(BaseModel):
    step: int
    added_candidate_id: uuid.UUID
    candidate_ids: list[uuid.UUID]
    score: ObjectiveScore
    marginal_net_gain: float | None
    additional_bytes: int | None
    gain_per_byte: float | None
    chosen: bool = False
    reason: str
    query_changes: list[QueryChange]


class CandidateOutcome(BaseModel):
    candidate_id: uuid.UUID
    selected: bool
    reason: str


class OptimizationResult(BaseModel):
    algorithm: Literal["greedy-marginal-v1"] = "greedy-marginal-v1"
    selected_candidate_ids: list[uuid.UUID]
    baseline: SetEstimate
    final: SetEstimate
    baseline_score: ObjectiveScore
    final_score: ObjectiveScore
    estimated_read_improvement_pct: float | None
    estimated_net_gain: float
    trials: list[Trial]
    candidates: list[CandidateOutcome]
    stop_reason: Literal[
        "no_candidates",
        "candidates_exhausted",
        "index_limit",
        "evaluation_limit",
        "no_feasible_gain",
    ]
    evaluations: int
    search_complete: bool
    final_verified: Literal[True] = True
    warnings: list[str]
    cost_unit: Literal["planner_cost"] = "planner_cost"
    execution_measured: Literal[False] = False


class OptimizationRunView(BaseModel):
    id: uuid.UUID
    evaluation_run_id: uuid.UUID
    batch_id: uuid.UUID
    created_at: datetime
    options: OptimizationOptions
    result: OptimizationResult
    cleanup_confirmed: bool
    context: dict


class OptimizationSummary(BaseModel):
    id: uuid.UUID
    evaluation_run_id: uuid.UUID
    created_at: datetime
