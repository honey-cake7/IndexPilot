"""Persist isolated benchmark jobs, approved inputs, arms and individual samples."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"


def upgrade():
    op.create_table(
        "benchmark_job",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recommendation_id", sa.Uuid(), sa.ForeignKey("recommendation_set.id"), nullable=False
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("request", JSONB(), nullable=False),
        sa.Column("manifest", JSONB(), nullable=False),
        sa.Column("result", JSONB()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("cleanup_confirmed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="benchmark_status",
        ),
    )
    op.create_table(
        "benchmark_query",
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("benchmark_job.id"), primary_key=True),
        sa.Column("source_plan_id", sa.Uuid(), sa.ForeignKey("plan_analysis.id"), primary_key=True),
        sa.Column("frequency", sa.Double(), nullable=False),
        sa.Column("canonical_sql", sa.Text(), nullable=False),
        sa.Column("analysis", JSONB(), nullable=False),
        sa.CheckConstraint("frequency>0 AND frequency<=1000000000", name="benchmark_frequency"),
    )
    op.create_table(
        "benchmark_candidate",
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("benchmark_job.id"), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("index_candidate.id"), primary_key=True),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "benchmark_arm_index",
        sa.Column("job_id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), primary_key=True),
        sa.Column("arm", sa.String(16), primary_key=True),
        sa.ForeignKeyConstraint(
            ["job_id", "candidate_id"],
            ["benchmark_candidate.job_id", "benchmark_candidate.candidate_id"],
        ),
        sa.CheckConstraint("arm IN ('per_query','indexpilot')", name="benchmark_arm"),
    )
    op.create_table(
        "benchmark_measurement",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("benchmark_job.id"), nullable=False),
        sa.Column("repetition", sa.Integer(), nullable=False),
        sa.Column("arm", sa.String(16), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False),
        sa.Column("conditions", JSONB(), nullable=False),
        sa.UniqueConstraint(
            "job_id", "repetition", "arm", "phase", name="benchmark_measurement_once"
        ),
        sa.CheckConstraint("repetition BETWEEN 0 AND 4", name="benchmark_repetition"),
        sa.CheckConstraint("arm IN ('baseline','per_query','indexpilot')", name="measurement_arm"),
    )
    op.create_table(
        "benchmark_sample",
        sa.Column(
            "measurement_id", sa.Uuid(), sa.ForeignKey("benchmark_measurement.id"), primary_key=True
        ),
        sa.Column("client_id", sa.Integer(), primary_key=True),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("script_id", sa.Integer(), nullable=False),
        sa.Column("latency_us", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "client_id>=0 AND sequence>=1 AND script_id>=0 AND latency_us>=0",
            name="benchmark_sample_values",
        ),
    )
    for table, columns in {
        "benchmark_job": ["recommendation_id", "created_at"],
        "benchmark_measurement": ["job_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in (
        "benchmark_sample",
        "benchmark_measurement",
        "benchmark_arm_index",
        "benchmark_candidate",
        "benchmark_query",
        "benchmark_job",
    ):
        op.drop_table(table)
