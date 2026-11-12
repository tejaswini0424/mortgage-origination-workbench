from alembic import op
import sqlalchemy as sa

revision = "0008_document_contents"
down_revision = "0007_vision_preference"

def upgrade():
    op.create_table(
        "document_contents",
        sa.Column("document_id", sa.String(32), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content", sa.LargeBinary(), nullable=False),
    )

def downgrade():
    op.drop_table("document_contents")
