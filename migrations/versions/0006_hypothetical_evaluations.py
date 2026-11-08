"""Persist completed/unavailable/failed hypothetical runs and normalized set evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"


def upgrade():
    op.create_table(
        "evaluation_run",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("candidate_batch.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("capability", JSONB(), nullable=False),
        sa.Column("requested_sets", JSONB(), nullable=False),
        sa.Column("context", JSONB(), nullable=False),
        sa.Column("warnings", JSONB(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("cleanup_confirmed", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "status IN ('completed','unavailable','failed')", name="evaluation_status"
        ),
    )
    op.create_table(
        "evaluation_query",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("evaluation_run.id"), nullable=False),
        sa.Column("source_plan_id", sa.Uuid(), sa.ForeignKey("plan_analysis.id"), nullable=False),
        sa.Column("frequency", sa.Double(), nullable=False),
        sa.Column("analysis", JSONB(), nullable=False),
        sa.UniqueConstraint("run_id", "source_plan_id", name="evaluation_query_source"),
        sa.CheckConstraint(
            "frequency>0 AND frequency<=1000000000", name="evaluation_query_frequency"
        ),
    )
    op.create_table(
        "index_evaluation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("evaluation_run.id"), nullable=False),
        sa.Column("set_signature", sa.String(64), nullable=False),
        sa.Column("is_baseline", sa.Boolean(), nullable=False),
        sa.Column("weighted_cost", sa.Double()),
        sa.Column("estimated_size_bytes", sa.BigInteger()),
        sa.Column("storage_complete", sa.Boolean(), nullable=False),
        sa.Column("warnings", JSONB(), nullable=False),
        sa.UniqueConstraint("run_id", "set_signature", name="evaluation_set_signature"),
        sa.CheckConstraint(
            "weighted_cost IS NULL OR (weighted_cost>=0 AND weighted_cost<'Infinity'::float8)",
            name="evaluation_cost",
        ),
        sa.CheckConstraint(
            "estimated_size_bytes IS NULL OR estimated_size_bytes>=0", name="evaluation_storage"
        ),
    )
    op.create_index(
        "uq_evaluation_baseline",
        "index_evaluation",
        ["run_id"],
        unique=True,
        postgresql_where=sa.text("is_baseline"),
    )
    op.create_table(
        "evaluation_member",
        sa.Column(
            "evaluation_id", sa.Uuid(), sa.ForeignKey("index_evaluation.id"), primary_key=True
        ),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("index_candidate.id"), primary_key=True),
        sa.Column("hypothetical_oid", sa.BigInteger(), nullable=False),
        sa.Column("hypothetical_name", sa.Text(), nullable=False),
        sa.Column("estimated_size_bytes", sa.BigInteger()),
        sa.CheckConstraint(
            "estimated_size_bytes IS NULL OR estimated_size_bytes>0", name="member_storage"
        ),
    )
    op.create_table(
        "evaluation_plan",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("evaluation_id", sa.Uuid(), sa.ForeignKey("index_evaluation.id"), nullable=False),
        sa.Column("query_id", sa.Uuid(), sa.ForeignKey("evaluation_query.id"), nullable=False),
        sa.Column("total_cost", sa.Double()),
        sa.Column("raw_explain", JSONB(), nullable=False),
        sa.UniqueConstraint("evaluation_id", "query_id", name="evaluation_plan_query"),
        sa.CheckConstraint(
            "total_cost IS NULL OR (total_cost>=0 AND total_cost<'Infinity'::float8)",
            name="evaluation_plan_cost",
        ),
    )
    for table, columns in {
        "evaluation_run": ["batch_id", "created_at"],
        "evaluation_query": ["run_id", "source_plan_id"],
        "index_evaluation": ["run_id"],
        "evaluation_member": ["candidate_id"],
        "evaluation_plan": ["evaluation_id", "query_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in (
        "evaluation_plan",
        "evaluation_member",
        "index_evaluation",
        "evaluation_query",
        "evaluation_run",
    ):
        op.drop_table(table)
