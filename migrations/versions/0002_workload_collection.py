"""Persist workload patterns/scenarios and raw cumulative statistics."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"


def upgrade():
    op.create_table(
        "workload",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("database_id", sa.Uuid(), sa.ForeignKey("monitored_database.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("source IN ('manual','pg_stat_statements')", name="workload_source"),
    )
    op.create_index("ix_workload_database_id", "workload", ["database_id"])
    op.create_table(
        "query_pattern",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workload_id", sa.Uuid(), sa.ForeignKey("workload.id"), nullable=False),
        sa.Column("identity", sa.String(100), nullable=False),
        sa.Column("fingerprint", sa.String(32), nullable=False),
        sa.Column("normalized_sql", sa.Text(), nullable=False),
        sa.Column("server_queryid", sa.BigInteger()),
        sa.Column("server_userid", sa.BigInteger()),
        sa.Column("server_dbid", sa.BigInteger()),
        sa.Column("server_toplevel", sa.Boolean()),
        sa.UniqueConstraint("workload_id", "identity", name="pattern_identity"),
    )
    op.create_index("ix_query_pattern_workload_id", "query_pattern", ["workload_id"])
    op.create_table(
        "query_scenario",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pattern_id", sa.Uuid(), sa.ForeignKey("query_pattern.id"), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("parameters", JSONB(), nullable=False),
        sa.Column("representative_sql", sa.Text()),
        sa.Column("missing_parameters", JSONB(), nullable=False),
        sa.Column("frequency", sa.Double(), nullable=False),
        sa.CheckConstraint("frequency > 0 AND frequency <= 1000000000", name="scenario_frequency"),
    )
    op.create_index("ix_query_scenario_pattern_id", "query_scenario", ["pattern_id"])
    op.create_table(
        "workload_snapshot",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workload_id", sa.Uuid(), sa.ForeignKey("workload.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("server_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stats_reset", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dealloc", sa.BigInteger(), nullable=False),
        sa.Column("dbid", sa.BigInteger(), nullable=False),
        sa.Column("extension_version", sa.String(32), nullable=False),
        sa.Column("consistent", sa.Boolean(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("skipped_statements", sa.Integer(), nullable=False),
        sa.Column("warnings", JSONB(), nullable=False),
        sa.CheckConstraint("dealloc >= 0 AND skipped_statements >= 0", name="snapshot_counters"),
    )
    op.create_index("ix_workload_snapshot_workload_id", "workload_snapshot", ["workload_id"])
    op.create_index("ix_workload_snapshot_observed_at", "workload_snapshot", ["observed_at"])
    op.create_table(
        "query_statistic",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("workload_snapshot.id"), nullable=False),
        sa.Column("pattern_id", sa.Uuid(), sa.ForeignKey("query_pattern.id"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("calls", sa.BigInteger(), nullable=False),
        sa.Column("total_exec_ms", sa.Double(), nullable=False),
        sa.Column("mean_exec_ms", sa.Double(), nullable=False),
        sa.Column("rows", sa.BigInteger(), nullable=False),
        sa.Column("buffers", JSONB(), nullable=False),
        sa.Column("stats_since", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("snapshot_id", "pattern_id", name="snapshot_pattern"),
        sa.CheckConstraint("calls >= 0 AND rows >= 0", name="statistic_counters"),
        sa.CheckConstraint(
            "total_exec_ms >= 0 AND total_exec_ms < 'Infinity'::float8 "
            "AND mean_exec_ms >= 0 AND mean_exec_ms < 'Infinity'::float8",
            name="statistic_times",
        ),
    )
    op.create_index("ix_query_statistic_snapshot_id", "query_statistic", ["snapshot_id"])
    op.create_index("ix_query_statistic_pattern_id", "query_statistic", ["pattern_id"])


def downgrade():
    for name in (
        "query_statistic",
        "workload_snapshot",
        "query_scenario",
        "query_pattern",
        "workload",
    ):
        op.drop_table(name)
