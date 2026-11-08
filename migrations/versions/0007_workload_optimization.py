"""Normalize optimization runs, candidate outcomes and evaluated trial choices."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"


def upgrade():
    op.create_table(
        "optimization_run",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "evaluation_run_id",
            sa.Uuid(),
            sa.ForeignKey("evaluation_run.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "final_evaluation_id", sa.Uuid(), sa.ForeignKey("index_evaluation.id"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("options", JSONB(), nullable=False),
        sa.Column("summary", JSONB(), nullable=False),
    )
    op.create_table(
        "optimization_candidate",
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("optimization_run.id"), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("index_candidate.id"), primary_key=True),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("selection_order", sa.Integer()),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.UniqueConstraint("run_id", "selection_order", name="optimization_selection_order"),
        sa.CheckConstraint(
            "(selected AND selection_order IS NOT NULL AND selection_order BETWEEN 1 AND 32) OR "
            "(NOT selected AND selection_order IS NULL)",
            name="optimization_selected_order",
        ),
    )
    op.create_table(
        "optimization_trial",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("optimization_run.id"), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), sa.ForeignKey("index_evaluation.id"), nullable=False),
        sa.Column(
            "added_candidate_id", sa.Uuid(), sa.ForeignKey("index_candidate.id"), nullable=False
        ),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("chosen", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False),
        sa.UniqueConstraint("run_id", "step", "added_candidate_id", name="optimization_trial_once"),
        sa.CheckConstraint("step BETWEEN 1 AND 32", name="optimization_trial_step"),
    )
    op.create_index(
        "uq_optimization_step_choice",
        "optimization_trial",
        ["run_id", "step"],
        unique=True,
        postgresql_where=sa.text("chosen"),
    )
    for table, columns in {
        "optimization_run": ["final_evaluation_id", "created_at"],
        "optimization_candidate": ["candidate_id"],
        "optimization_trial": ["run_id", "evaluation_id", "added_candidate_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    op.drop_table("optimization_trial")
    op.drop_table("optimization_candidate")
    op.drop_table("optimization_run")
