"""Persist immutable, versioned report documents independently of later source changes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"


def upgrade():
    op.create_table(
        "saved_report",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recommendation_id", sa.Uuid(), sa.ForeignKey("recommendation_set.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("format_version", sa.String(40), nullable=False),
        sa.Column("document", JSONB(), nullable=False),
        sa.CheckConstraint("format_version = 'indexpilot-report-v1'", name="report_format_version"),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 120", name="report_title_length"),
    )
    op.create_index("ix_saved_report_recommendation_id", "saved_report", ["recommendation_id"])
    op.create_index("ix_saved_report_created_at", "saved_report", ["created_at"])


def downgrade():
    op.drop_table("saved_report")
