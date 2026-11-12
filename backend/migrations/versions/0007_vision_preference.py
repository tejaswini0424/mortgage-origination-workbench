"""Store the organization's document vision preference."""

from alembic import op
import sqlalchemy as sa

revision = "0007_vision_preference"
down_revision = "0006_benchmark_status"

def upgrade():
    op.add_column("organizations", sa.Column("document_vision", sa.Boolean(), nullable=False, server_default=sa.true()))

def downgrade():
    op.drop_column("organizations", "document_vision")
