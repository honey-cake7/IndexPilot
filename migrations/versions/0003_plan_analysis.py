"""Save estimated execution plans with resolved schema/query provenance."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"


def upgrade():
    op.create_table(
        "plan_analysis",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("database_id", sa.Uuid(), sa.ForeignKey("monitored_database.id"), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), sa.ForeignKey("query_scenario.id")),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("database_name", sa.String(63), nullable=False),
        sa.Column("server_version", sa.String(120), nullable=False),
        sa.Column("original_sql", sa.Text(), nullable=False),
        sa.Column("frequency", sa.Double(), nullable=False),
        sa.Column("analysis", JSONB(), nullable=False),
        sa.Column("raw_explain", JSONB(), nullable=False),
        sa.Column("planner_settings", JSONB(), nullable=False),
        sa.Column("root_node_type", sa.String(80), nullable=False),
        sa.Column("total_cost", sa.Double()),
        sa.CheckConstraint("frequency > 0 AND frequency <= 1000000000", name="plan_frequency"),
        sa.CheckConstraint(
            "total_cost IS NULL OR (total_cost >= 0 AND total_cost < 'Infinity'::float8)",
            name="plan_cost",
        ),
    )
    for name in ("database_id", "scenario_id", "captured_at"):
        op.create_index(f"ix_plan_analysis_{name}", "plan_analysis", [name])


def downgrade():
    op.drop_table("plan_analysis")
