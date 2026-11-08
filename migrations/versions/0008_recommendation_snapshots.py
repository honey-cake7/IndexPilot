"""Freeze recommendation explanations, selected indexes, queries and scoped evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"


def upgrade():
    op.create_table(
        "recommendation_set",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "optimization_id",
            sa.Uuid(),
            sa.ForeignKey("optimization_run.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("explanation_version", sa.String(64), nullable=False),
        *(
            sa.Column(name, JSONB(), nullable=False)
            for name in ("provenance", "options", "summary", "warnings")
        ),
    )
    op.create_table(
        "recommendation_set_index",
        sa.Column(
            "recommendation_id", sa.Uuid(), sa.ForeignKey("recommendation_set.id"), primary_key=True
        ),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("index_candidate.id"), primary_key=True),
        sa.Column(
            "source_trial_id", sa.Uuid(), sa.ForeignKey("optimization_trial.id"), nullable=False
        ),
        sa.Column("selection_order", sa.Integer(), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("estimated_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("explanation", JSONB(), nullable=False),
        sa.Column("deployment_sql", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "recommendation_id", "selection_order", name="recommendation_index_order"
        ),
        sa.UniqueConstraint(
            "recommendation_id", "source_trial_id", name="recommendation_index_trial"
        ),
        sa.CheckConstraint(
            "selection_order BETWEEN 1 AND 32", name="recommendation_selection_order"
        ),
        sa.CheckConstraint("estimated_size_bytes>0", name="recommendation_index_bytes"),
    )
    op.create_table(
        "recommendation_query",
        sa.Column(
            "recommendation_id", sa.Uuid(), sa.ForeignKey("recommendation_set.id"), primary_key=True
        ),
        sa.Column("source_plan_id", sa.Uuid(), sa.ForeignKey("plan_analysis.id"), primary_key=True),
        sa.Column(
            "evaluation_query_id", sa.Uuid(), sa.ForeignKey("evaluation_query.id"), nullable=False
        ),
        sa.Column("frequency", sa.Double(), nullable=False),
        sa.Column("original_sql", sa.Text(), nullable=False),
        *(
            sa.Column(name, JSONB(), nullable=False)
            for name in (
                "analysis",
                "baseline_raw_explain",
                "hypothetical_raw_explain",
                "explanation",
            )
        ),
        sa.UniqueConstraint(
            "recommendation_id", "evaluation_query_id", name="recommendation_query_once"
        ),
        sa.CheckConstraint(
            "frequency>0 AND frequency<=1000000000", name="recommendation_query_frequency"
        ),
    )
    op.create_table(
        "recommendation_index_query",
        sa.Column("recommendation_id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), primary_key=True),
        sa.Column("source_plan_id", sa.Uuid(), primary_key=True),
        sa.Column("proposed_evidence", JSONB(), nullable=False),
        sa.Column("used_in_final_plan", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recommendation_id", "candidate_id"],
            ["recommendation_set_index.recommendation_id", "recommendation_set_index.candidate_id"],
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id", "source_plan_id"],
            ["recommendation_query.recommendation_id", "recommendation_query.source_plan_id"],
        ),
    )
    for table, columns in {
        "recommendation_set": ["created_at"],
        "recommendation_set_index": ["candidate_id", "source_trial_id"],
        "recommendation_query": ["source_plan_id", "evaluation_query_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in (
        "recommendation_index_query",
        "recommendation_query",
        "recommendation_set_index",
        "recommendation_set",
    ):
        op.drop_table(table)
