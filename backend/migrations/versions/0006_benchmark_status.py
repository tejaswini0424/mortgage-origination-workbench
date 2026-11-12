"""Track persisted research jobs."""

from alembic import op
import sqlalchemy as sa

revision = "0006_benchmark_status"
down_revision = "0005_benchmarks"

def upgrade():
    op.add_column("benchmark_runs", sa.Column("status", sa.String(20), nullable=False, server_default="completed"))
    op.create_index("ix_benchmark_runs_status", "benchmark_runs", ["status"])

def downgrade():
    op.drop_index("ix_benchmark_runs_status", table_name="benchmark_runs")
    op.drop_column("benchmark_runs", "status")
