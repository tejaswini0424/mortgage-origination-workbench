"""Persist organization-scoped benchmark reports."""

from alembic import op
import sqlalchemy as sa

revision = "0005_benchmarks"
down_revision = "0004_worksheets"

def upgrade():
    op.create_table("benchmark_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("organization", sa.String(64), sa.ForeignKey("organizations.slug"), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False))
    op.create_index("ix_benchmark_runs_organization", "benchmark_runs", ["organization"])

def downgrade():
    op.drop_table("benchmark_runs")
