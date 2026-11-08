import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
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
