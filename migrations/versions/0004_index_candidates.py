"""Persist bounded candidate batches, plan membership and candidate decisions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"


def upgrade():
    op.create_table(
        "candidate_batch",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("database_id", sa.Uuid(), sa.ForeignKey("monitored_database.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("catalog_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("options", JSONB(), nullable=False),
        sa.Column("algorithm_version", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("unique_considered", sa.Integer(), nullable=False),
        sa.Column("search_truncated", sa.Boolean(), nullable=False),
        sa.Column("warnings", JSONB(), nullable=False),
        sa.CheckConstraint(
            "attempts >= 0 AND unique_considered >= 0", name="candidate_batch_counts"
        ),
    )
    for column in ("database_id", "created_at"):
        op.create_index(f"ix_candidate_batch_{column}", "candidate_batch", [column])
    op.create_table(
        "candidate_batch_source",
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("candidate_batch.id"), primary_key=True),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("plan_analysis.id"), primary_key=True),
    )
    op.create_table(
        "index_candidate",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("candidate_batch.id"), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rejection_reason", sa.String(64)),
        sa.Column("existing_indexes", JSONB(), nullable=False),
        sa.Column("warnings", JSONB(), nullable=False),
        sa.Column("evidence", JSONB(), nullable=False),
        sa.UniqueConstraint("batch_id", "signature", name="candidate_signature"),
        sa.CheckConstraint(
            "(status='proposed' AND rejection_reason IS NULL) OR "
            "(status='rejected' AND rejection_reason IS NOT NULL)",
            name="candidate_status",
        ),
    )
    op.create_index("ix_index_candidate_batch_id", "index_candidate", ["batch_id"])


def downgrade():
    op.drop_table("index_candidate")
    op.drop_table("candidate_batch_source")
    op.drop_table("candidate_batch")
