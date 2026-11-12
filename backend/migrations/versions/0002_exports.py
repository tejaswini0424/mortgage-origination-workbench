"""Preserve released case packet history."""

from alembic import op
import sqlalchemy as sa

revision = "0002_exports"
down_revision = "0001_workbench"

def upgrade():
    op.create_table("case_exports",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("case_id", sa.String(32), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("packet", sa.JSON(), nullable=False))
    op.create_index("ix_case_exports_case_id", "case_exports", ["case_id"])

def downgrade():
    op.drop_table("case_exports")
