"""Normalize per-candidate query evidence, preserving existing prototype records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"


def upgrade():
    op.create_table(
        "index_candidate_evidence",
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("index_candidate.id"), primary_key=True),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("plan_analysis.id"), primary_key=True),
        sa.Column("query_alias", sa.String(63), primary_key=True),
        sa.Column("reason", sa.String(32), primary_key=True),
        sa.Column("explanation", sa.Text(), nullable=False),
    )
    op.create_index("ix_index_candidate_evidence_plan_id", "index_candidate_evidence", ["plan_id"])
    op.execute("""
      INSERT INTO index_candidate_evidence(candidate_id,plan_id,query_alias,reason,explanation)
      SELECT c.id,(e->>'plan_id')::uuid,e->>'alias',e->>'reason',e->>'explanation'
      FROM index_candidate c CROSS JOIN LATERAL jsonb_array_elements(c.evidence) e
    """)
    op.drop_column("index_candidate", "evidence")


def downgrade():
    op.add_column(
        "index_candidate",
        sa.Column("evidence", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.execute("""
      UPDATE index_candidate c SET evidence=aggregated.evidence FROM (
       SELECT candidate_id,jsonb_agg(jsonb_build_object('plan_id',plan_id,'alias',query_alias,
        'reason',reason,'explanation',explanation) ORDER BY plan_id,query_alias,reason) AS evidence
       FROM index_candidate_evidence GROUP BY candidate_id
      ) aggregated WHERE c.id=aggregated.candidate_id
    """)
    op.alter_column("index_candidate", "evidence", server_default=None)
    op.drop_table("index_candidate_evidence")
