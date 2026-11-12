"""Create the initial workbench schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001_workbench"
down_revision = None

def upgrade():
    op.create_table("cases",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("borrower", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("calculation", sa.JSON(), nullable=True),
        sa.Column("packet", sa.JSON(), nullable=True))
    op.create_table("documents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("case_id", sa.String(32), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("media", sa.String(32), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False))
    op.create_index("ix_documents_case_id", "documents", ["case_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

def downgrade():
    op.drop_table("documents")
    op.drop_table("cases")
