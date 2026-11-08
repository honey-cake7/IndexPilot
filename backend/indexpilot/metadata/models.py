import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MonitoredDatabase(Base):
    __tablename__ = "monitored_database"
    __table_args__ = (CheckConstraint("port BETWEEN 1 AND 65535", name="valid_port"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    target_key: Mapped[str] = mapped_column(String(80), unique=True)
    host: Mapped[str] = mapped_column(String(253))
    port: Mapped[int] = mapped_column(Integer)
    database_name: Mapped[str] = mapped_column(String(63))
    role_name: Mapped[str] = mapped_column(String(63))
    credential_reference: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Workload(Base):
    __tablename__ = "workload"
    __table_args__ = (
        CheckConstraint("source IN ('manual','pg_stat_statements')", name="workload_source"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    database_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitored_database.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QueryPattern(Base):
    __tablename__ = "query_pattern"
    __table_args__ = (UniqueConstraint("workload_id", "identity", name="pattern_identity"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workload.id"), index=True)
    identity: Mapped[str] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(32))
    normalized_sql: Mapped[str] = mapped_column(Text)
    server_queryid: Mapped[int | None] = mapped_column(BigInteger)
    server_userid: Mapped[int | None] = mapped_column(BigInteger)
    server_dbid: Mapped[int | None] = mapped_column(BigInteger)
    server_toplevel: Mapped[bool | None]


class QueryScenario(Base):
    __tablename__ = "query_scenario"
    __table_args__ = (
        CheckConstraint(
            "frequency > 0 AND frequency <= 1000000000",
            name="scenario_frequency",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pattern_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("query_pattern.id"), index=True)
    sql: Mapped[str] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(JSONB)
    representative_sql: Mapped[str | None] = mapped_column(Text)
    missing_parameters: Mapped[list] = mapped_column(JSONB)
    frequency: Mapped[float] = mapped_column(Double)


class WorkloadSnapshot(Base):
    __tablename__ = "workload_snapshot"
    __table_args__ = (
        CheckConstraint("dealloc >= 0 AND skipped_statements >= 0", name="snapshot_counters"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workload.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    server_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stats_reset: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dealloc: Mapped[int] = mapped_column(BigInteger)
    dbid: Mapped[int] = mapped_column(BigInteger)
    extension_version: Mapped[str] = mapped_column(String(32))
    consistent: Mapped[bool]
    truncated: Mapped[bool]
    skipped_statements: Mapped[int] = mapped_column(Integer)
    warnings: Mapped[list] = mapped_column(JSONB)


class QueryStatistic(Base):
    __tablename__ = "query_statistic"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "pattern_id", name="snapshot_pattern"),
        CheckConstraint("calls >= 0 AND rows >= 0", name="statistic_counters"),
        CheckConstraint(
            "total_exec_ms >= 0 AND total_exec_ms < 'Infinity'::float8 "
            "AND mean_exec_ms >= 0 AND mean_exec_ms < 'Infinity'::float8",
            name="statistic_times",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workload_snapshot.id"), index=True)
    pattern_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("query_pattern.id"), index=True)
    query: Mapped[str] = mapped_column(Text)
    calls: Mapped[int] = mapped_column(BigInteger)
    total_exec_ms: Mapped[float] = mapped_column(Double)
    mean_exec_ms: Mapped[float] = mapped_column(Double)
    rows: Mapped[int] = mapped_column(BigInteger)
    buffers: Mapped[dict] = mapped_column(JSONB)
    stats_since: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlanAnalysis(Base):
    __tablename__ = "plan_analysis"
    __table_args__ = (
        CheckConstraint("frequency > 0 AND frequency <= 1000000000", name="plan_frequency"),
        CheckConstraint(
            "total_cost IS NULL OR (total_cost >= 0 AND total_cost < 'Infinity'::float8)",
            name="plan_cost",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    database_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitored_database.id"), index=True)
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("query_scenario.id"), index=True
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    database_name: Mapped[str] = mapped_column(String(63))
    server_version: Mapped[str] = mapped_column(String(120))
    original_sql: Mapped[str] = mapped_column(Text)
    frequency: Mapped[float] = mapped_column(Double)
    analysis: Mapped[dict] = mapped_column(JSONB)
    raw_explain: Mapped[list] = mapped_column(JSONB)
    planner_settings: Mapped[dict] = mapped_column(JSONB)
    root_node_type: Mapped[str] = mapped_column(String(80))
    total_cost: Mapped[float | None] = mapped_column(Double)


class CandidateBatch(Base):
    __tablename__ = "candidate_batch"
    __table_args__ = (
        CheckConstraint("attempts >= 0 AND unique_considered >= 0", name="candidate_batch_counts"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    database_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitored_database.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    catalog_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    options: Mapped[dict] = mapped_column(JSONB)
    algorithm_version: Mapped[str] = mapped_column(String(32))
    attempts: Mapped[int] = mapped_column(Integer)
    unique_considered: Mapped[int] = mapped_column(Integer)
    search_truncated: Mapped[bool]
    warnings: Mapped[list] = mapped_column(JSONB)


class CandidateBatchSource(Base):
    __tablename__ = "candidate_batch_source"
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_batch.id"), primary_key=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_analysis.id"), primary_key=True)


class IndexCandidate(Base):
    __tablename__ = "index_candidate"
    __table_args__ = (
        UniqueConstraint("batch_id", "signature", name="candidate_signature"),
        CheckConstraint(
            "(status='proposed' AND rejection_reason IS NULL) OR "
            "(status='rejected' AND rejection_reason IS NOT NULL)",
            name="candidate_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_batch.id"), index=True)
    signature: Mapped[str] = mapped_column(String(64))
    definition: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    rejection_reason: Mapped[str | None] = mapped_column(String(64))
    existing_indexes: Mapped[list] = mapped_column(JSONB)
    warnings: Mapped[list] = mapped_column(JSONB)


class IndexCandidateEvidence(Base):
    __tablename__ = "index_candidate_evidence"
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("index_candidate.id"), primary_key=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plan_analysis.id"), primary_key=True, index=True
    )
    query_alias: Mapped[str] = mapped_column(String(63), primary_key=True)
    reason: Mapped[str] = mapped_column(String(32), primary_key=True)
    explanation: Mapped[str] = mapped_column(Text)


class EvaluationRun(Base):
    __tablename__ = "evaluation_run"
    __table_args__ = (
        CheckConstraint("status IN ('completed','unavailable','failed')", name="evaluation_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_batch.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    status: Mapped[str] = mapped_column(String(16))
    capability: Mapped[dict] = mapped_column(JSONB)
    requested_sets: Mapped[list] = mapped_column(JSONB)
    context: Mapped[dict] = mapped_column(JSONB)
    warnings: Mapped[list] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    cleanup_confirmed: Mapped[bool]


class EvaluationQuery(Base):
    __tablename__ = "evaluation_query"
    __table_args__ = (
        UniqueConstraint("run_id", "source_plan_id", name="evaluation_query_source"),
        CheckConstraint("frequency>0 AND frequency<=1000000000", name="evaluation_query_frequency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_run.id"), index=True)
    source_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_analysis.id"), index=True)
    frequency: Mapped[float] = mapped_column(Double)
    analysis: Mapped[dict] = mapped_column(JSONB)


class IndexEvaluation(Base):
    __tablename__ = "index_evaluation"
    __table_args__ = (
        UniqueConstraint("run_id", "set_signature", name="evaluation_set_signature"),
        CheckConstraint(
            "weighted_cost IS NULL OR (weighted_cost>=0 AND weighted_cost<'Infinity'::float8)",
            name="evaluation_cost",
        ),
        CheckConstraint(
            "estimated_size_bytes IS NULL OR estimated_size_bytes>=0", name="evaluation_storage"
        ),
        Index(
            "uq_evaluation_baseline", "run_id", unique=True, postgresql_where=sa_text("is_baseline")
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_run.id"), index=True)
    set_signature: Mapped[str] = mapped_column(String(64))
    is_baseline: Mapped[bool]
    weighted_cost: Mapped[float | None] = mapped_column(Double)
    estimated_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    storage_complete: Mapped[bool]
    warnings: Mapped[list] = mapped_column(JSONB)


class EvaluationMember(Base):
    __tablename__ = "evaluation_member"
    __table_args__ = (
        CheckConstraint(
            "estimated_size_bytes IS NULL OR estimated_size_bytes>0", name="member_storage"
        ),
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("index_evaluation.id"), primary_key=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("index_candidate.id"), primary_key=True, index=True
    )
    hypothetical_oid: Mapped[int] = mapped_column(BigInteger)
    hypothetical_name: Mapped[str] = mapped_column(Text)
    estimated_size_bytes: Mapped[int | None] = mapped_column(BigInteger)


class EvaluationPlan(Base):
    __tablename__ = "evaluation_plan"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "query_id", name="evaluation_plan_query"),
        CheckConstraint(
            "total_cost IS NULL OR (total_cost>=0 AND total_cost<'Infinity'::float8)",
            name="evaluation_plan_cost",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("index_evaluation.id"), index=True)
    query_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_query.id"), index=True)
    total_cost: Mapped[float | None] = mapped_column(Double)
    raw_explain: Mapped[list] = mapped_column(JSONB)


class OptimizationRun(Base):
    __tablename__ = "optimization_run"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_run.id"), unique=True
    )
    final_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("index_evaluation.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    options: Mapped[dict] = mapped_column(JSONB)
    summary: Mapped[dict] = mapped_column(JSONB)


class OptimizationCandidate(Base):
    __tablename__ = "optimization_candidate"
    __table_args__ = (
        UniqueConstraint("run_id", "selection_order", name="optimization_selection_order"),
        CheckConstraint(
            "(selected AND selection_order IS NOT NULL AND selection_order BETWEEN 1 AND 32) OR "
            "(NOT selected AND selection_order IS NULL)",
            name="optimization_selected_order",
        ),
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("optimization_run.id"), primary_key=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("index_candidate.id"), primary_key=True, index=True
    )
    selected: Mapped[bool]
    selection_order: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(64))


class OptimizationTrial(Base):
    __tablename__ = "optimization_trial"
    __table_args__ = (
        UniqueConstraint("run_id", "step", "added_candidate_id", name="optimization_trial_once"),
        CheckConstraint("step BETWEEN 1 AND 32", name="optimization_trial_step"),
        Index(
            "uq_optimization_step_choice",
            "run_id",
            "step",
            unique=True,
            postgresql_where=sa_text("chosen"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("optimization_run.id"), index=True)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("index_evaluation.id"), index=True)
    added_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("index_candidate.id"), index=True
    )
    step: Mapped[int]
    chosen: Mapped[bool]
    reason: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[dict] = mapped_column(JSONB)


class RecommendationSet(Base):
    __tablename__ = "recommendation_set"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    optimization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("optimization_run.id"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    explanation_version: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[dict] = mapped_column(JSONB)
    options: Mapped[dict] = mapped_column(JSONB)
    summary: Mapped[dict] = mapped_column(JSONB)
    warnings: Mapped[list] = mapped_column(JSONB)


class RecommendationSetIndex(Base):
    __tablename__ = "recommendation_set_index"
    __table_args__ = (
        UniqueConstraint("recommendation_id", "selection_order", name="recommendation_index_order"),
        UniqueConstraint("recommendation_id", "source_trial_id", name="recommendation_index_trial"),
        CheckConstraint("selection_order BETWEEN 1 AND 32", name="recommendation_selection_order"),
        CheckConstraint("estimated_size_bytes>0", name="recommendation_index_bytes"),
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendation_set.id"), primary_key=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("index_candidate.id"), primary_key=True, index=True
    )
    source_trial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("optimization_trial.id"), index=True
    )
    selection_order: Mapped[int]
    definition: Mapped[dict] = mapped_column(JSONB)
    estimated_size_bytes: Mapped[int] = mapped_column(BigInteger)
    explanation: Mapped[dict] = mapped_column(JSONB)
    deployment_sql: Mapped[str] = mapped_column(Text)


class RecommendationQuery(Base):
    __tablename__ = "recommendation_query"
    __table_args__ = (
        CheckConstraint(
            "frequency>0 AND frequency<=1000000000", name="recommendation_query_frequency"
        ),
        UniqueConstraint(
            "recommendation_id", "evaluation_query_id", name="recommendation_query_once"
        ),
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendation_set.id"), primary_key=True
    )
    source_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plan_analysis.id"), primary_key=True, index=True
    )
    evaluation_query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_query.id"), index=True
    )
    frequency: Mapped[float] = mapped_column(Double)
    original_sql: Mapped[str] = mapped_column(Text)
    analysis: Mapped[dict] = mapped_column(JSONB)
    baseline_raw_explain: Mapped[list] = mapped_column(JSONB)
    hypothetical_raw_explain: Mapped[list] = mapped_column(JSONB)
    explanation: Mapped[dict] = mapped_column(JSONB)


class RecommendationIndexQuery(Base):
    __tablename__ = "recommendation_index_query"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recommendation_id", "candidate_id"],
            ["recommendation_set_index.recommendation_id", "recommendation_set_index.candidate_id"],
        ),
        ForeignKeyConstraint(
            ["recommendation_id", "source_plan_id"],
            ["recommendation_query.recommendation_id", "recommendation_query.source_plan_id"],
        ),
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    source_plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    proposed_evidence: Mapped[list] = mapped_column(JSONB)
    used_in_final_plan: Mapped[bool]


class BenchmarkJob(Base):
    __tablename__ = "benchmark_job"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="benchmark_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendation_set.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(16))
    request: Mapped[dict] = mapped_column(JSONB)
    manifest: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    cleanup_confirmed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BenchmarkQuery(Base):
    __tablename__ = "benchmark_query"
    __table_args__ = (
        CheckConstraint("frequency>0 AND frequency<=1000000000", name="benchmark_frequency"),
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_job.id"), primary_key=True)
    source_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plan_analysis.id"), primary_key=True
    )
    frequency: Mapped[float] = mapped_column(Double)
    canonical_sql: Mapped[str] = mapped_column(Text)
    analysis: Mapped[dict] = mapped_column(JSONB)


class BenchmarkCandidate(Base):
    __tablename__ = "benchmark_candidate"
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_job.id"), primary_key=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("index_candidate.id"), primary_key=True
    )
    definition: Mapped[dict] = mapped_column(JSONB)
    selected: Mapped[bool]


class BenchmarkArmIndex(Base):
    __tablename__ = "benchmark_arm_index"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "candidate_id"],
            ["benchmark_candidate.job_id", "benchmark_candidate.candidate_id"],
        ),
        CheckConstraint("arm IN ('per_query','indexpilot')", name="benchmark_arm"),
    )
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    arm: Mapped[str] = mapped_column(String(16), primary_key=True)


class BenchmarkMeasurement(Base):
    __tablename__ = "benchmark_measurement"
    __table_args__ = (
        UniqueConstraint("job_id", "repetition", "arm", "phase", name="benchmark_measurement_once"),
        CheckConstraint("repetition BETWEEN 0 AND 4", name="benchmark_repetition"),
        CheckConstraint("arm IN ('baseline','per_query','indexpilot')", name="measurement_arm"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_job.id"), index=True)
    repetition: Mapped[int]
    arm: Mapped[str] = mapped_column(String(16))
    phase: Mapped[str] = mapped_column(String(32))
    metrics: Mapped[dict] = mapped_column(JSONB)
    conditions: Mapped[dict] = mapped_column(JSONB)


class BenchmarkSample(Base):
    __tablename__ = "benchmark_sample"
    __table_args__ = (
        CheckConstraint(
            "client_id>=0 AND sequence>=1 AND script_id>=0 AND latency_us>=0",
            name="benchmark_sample_values",
        ),
    )
    measurement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_measurement.id"), primary_key=True
    )
    client_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int]
    latency_us: Mapped[int] = mapped_column(BigInteger)
