import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from indexpilot.candidates.models import CandidateEvidence, CandidateKey
from indexpilot.optimizer.models import ObjectiveScore, OptimizationOptions
from indexpilot.plans.models import PlanDocument


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    optimization_id: uuid.UUID


class IndexSpecification(BaseModel):
    signature: str
    schema_name: str
    table_name: str
    table_oid: int
    index_name: str
    method: Literal["btree"]
    keys: list[CandidateKey]


class PlanComparison(BaseModel):
    baseline_node_types: list[str]
    final_node_types: list[str]
    baseline_index_names: list[str]
    final_used_candidate_ids: list[uuid.UUID]
    observations: list[str]


class QueryExplanation(BaseModel):
    baseline_cost: float
    final_cost: float
    estimated_cost_reduction: float
    estimated_improvement_pct: float | None
    baseline_weighted_cost: float
    final_weighted_cost: float
    estimated_weighted_cost_reduction: float
    contribution_to_baseline_pct: float | None
    regression: bool
    comparison: PlanComparison
    warnings: list[str]


class StatisticsObservation(BaseModel):
    relation_oid: int
    schema_name: str
    table_name: str
    last_analyze: datetime | None
    last_autoanalyze: datetime | None


class RecommendedQuery(BaseModel):
    source_plan_id: uuid.UUID
    original_sql: str
    representative_sql: str
    frequency: float
    statistics_observations: list[StatisticsObservation]
    baseline_plan: PlanDocument
    hypothetical_plan: PlanDocument
    baseline_raw_explain: list[dict]
    hypothetical_raw_explain: list[dict]
    explanation: QueryExplanation


class RelevantQuery(BaseModel):
    source_plan_id: uuid.UUID
    proposed_evidence: list[CandidateEvidence]
    used_in_final_plan: bool


class IndexExplanation(BaseModel):
    selection_reason: str
    selection_step_read_cost_reduction: float
    selection_step_net_gain: float
    selection_step_penalty_increase: float
    gain_per_additional_byte: float
    attribution: Literal["selection_step_marginal"] = "selection_step_marginal"
    write_overhead: str
    warnings: list[str]


class RecommendedIndex(BaseModel):
    candidate_id: uuid.UUID
    selection_order: int
    source_trial_id: uuid.UUID
    definition: IndexSpecification
    estimated_size_bytes: int
    relevant_queries: list[RelevantQuery]
    explanation: IndexExplanation


class RecommendationSummaryData(BaseModel):
    selected_count: int
    storage_budget_bytes: int
    estimated_size_bytes: int
    baseline_score: ObjectiveScore
    final_score: ObjectiveScore
    estimated_read_improvement_pct: float | None
    estimated_net_gain: float
    stop_reason: str
    search_complete: bool
    evaluations: int
    message: str


class RecommendationView(BaseModel):
    id: uuid.UUID
    optimization_id: uuid.UUID
    created_at: datetime
    explanation_version: str
    provenance: dict
    options: OptimizationOptions
    summary: RecommendationSummaryData
    indexes: list[RecommendedIndex]
    queries: list[RecommendedQuery]
    warnings: list[str]
    evidence_level: Literal["planner_estimate"] = "planner_estimate"
    execution_measured: Literal[False] = False
    benchmark_outcome: None = None
    cost_unit: Literal["planner_cost"] = "planner_cost"


class RecommendationSummary(BaseModel):
    id: uuid.UUID
    optimization_id: uuid.UUID
    created_at: datetime
    selected_count: int
    estimated_size_bytes: int
    estimated_read_improvement_pct: float | None


class DeploymentStatement(BaseModel):
    candidate_id: uuid.UUID
    sql: str


class DeploymentSQL(BaseModel):
    recommendation_id: uuid.UUID
    statements: list[DeploymentStatement]
    warnings: list[str]
    requires_human_review: Literal[True] = True
    executed: Literal[False] = False
