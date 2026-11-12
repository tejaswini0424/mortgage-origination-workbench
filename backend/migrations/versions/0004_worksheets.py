"""Store case parties and worksheet inputs."""

from alembic import op
import sqlalchemy as sa

revision = "0004_worksheets"
down_revision = "0003_access"

def upgrade():
    op.create_table("case_worksheets",
        sa.Column("case_id", sa.String(32), sa.ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("section", sa.String(32), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False))

def downgrade():
    op.drop_table("case_worksheets")
