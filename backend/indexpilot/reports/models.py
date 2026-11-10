import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from indexpilot.candidates.models import CandidateKey
from indexpilot.optimizer.models import OptimizationOptions, Trial
from indexpilot.recommendations.models import (
    IndexExplanation,
    QueryExplanation,
    RecommendationSummaryData,
    StatisticsObservation,
)

VERSION = "indexpilot-report-v1"


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation_id: uuid.UUID
    title: str = Field(
        default="Optimization report", min_length=1, max_length=120, pattern=r"^[^\x00-\x1f\x7f]+$"
    )
    benchmark_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)
    include_original_sql: bool = Field(default=True, strict=True)
    include_representative_sql: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def valid_policy(self):
        self.title = self.title.strip()
        if not self.title or len(set(self.benchmark_ids)) != len(self.benchmark_ids):
            raise ValueError("Use a nonempty title and distinct benchmark IDs")
        if self.include_representative_sql and not self.include_original_sql:
            raise ValueError("Representative SQL requires original SQL inclusion")
        return self


class ReportPolicy(BaseModel):
    original_sql_included: bool
    representative_sql_included: bool
    parameter_policy: str


class ReportQuery(BaseModel):
    source_plan_id: uuid.UUID
    frequency: float
    original_sql: str | None
    representative_sql: str | None
    explanation: QueryExplanation
    statistics: list[StatisticsObservation]


class ReportIndex(BaseModel):
    candidate_id: uuid.UUID
    schema_name: str
    table_name: str
    index_name: str
    keys: list[CandidateKey]
    estimated_size_bytes: int
    explanation: IndexExplanation
    deployment_sql: str | None


class ReportCandidate(BaseModel):
    candidate_id: uuid.UUID
    schema_name: str
    table_name: str
    keys: list[CandidateKey]
    generation_status: str
    selected: bool
    reason: str


class ReportMetrics(BaseModel):
    samples: int
    mean_ms: float | None
    median_ms: float | None
    p95_ms: float | None
    tps: float | None
    latency_unit: str
    throughput_unit: str
    percentile_method: str
    transaction_definition: str


class ReportMeasurement(BaseModel):
    id: uuid.UUID
    repetition: int
    arm: str
    phase: str
    metrics: ReportMetrics
    conditions: dict


class ReportComparison(BaseModel):
    phase: str
    arm: str
    baseline_mean_ms: float
    mean_ms: float
    repetitions: int
    baseline_repetition_stddev_ms: float | None
    repetition_stddev_ms: float | None
    measured_improvement_pct: float | None
    regression: bool | None


class ReportBenchmark(BaseModel):
    id: uuid.UUID
    status: str
    cleanup_confirmed: bool
    complete_comparison: bool
    created_at: str
    finished_at: str | None
    request: dict
    conditions: dict
    measurements: list[ReportMeasurement]
    comparisons: list[ReportComparison]
    warnings: list[str]
    error_code: str | None


class ReportDocument(BaseModel):
    id: uuid.UUID
    format_version: Literal["indexpilot-report-v1"] = VERSION
    created_at: datetime
    title: str
    recommendation_id: uuid.UUID
    optimization_id: uuid.UUID
    batch_id: uuid.UUID
    policy: ReportPolicy
    summary: RecommendationSummaryData
    settings: OptimizationOptions
    provenance: dict
    queries: list[ReportQuery]
    indexes: list[ReportIndex]
    candidates: list[ReportCandidate]
    search_trials: list[Trial]
    benchmarks: list[ReportBenchmark]
    missing_evidence: list[str]
    warnings: list[str]
    cost_unit: Literal["planner_cost"] = "planner_cost"
    size_unit: Literal["bytes"] = "bytes"
    latency_unit: Literal["ms"] = "ms"
    throughput_unit: Literal["transactions/second"] = "transactions/second"


class ReportSummary(BaseModel):
    id: uuid.UUID
    recommendation_id: uuid.UUID
    created_at: datetime
    title: str
    format_version: str


class ReportPage(BaseModel):
    items: list[ReportSummary]
    total: int
    limit: int
    offset: int
