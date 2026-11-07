"""Create safe monitored-database identities without credential values."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "monitored_database",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("target_key", sa.String(80), nullable=False, unique=True),
        sa.Column("host", sa.String(253), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database_name", sa.String(63), nullable=False),
        sa.Column("role_name", sa.String(63), nullable=False),
        sa.Column("credential_reference", sa.String(80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("port BETWEEN 1 AND 65535", name="valid_port"),
    )


def downgrade():
    op.drop_table("monitored_database")
