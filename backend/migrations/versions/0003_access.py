"""Add organization and case access scope."""

from alembic import op
import sqlalchemy as sa

revision = "0003_access"
down_revision = "0002_exports"

def upgrade():
    organizations = op.create_table("organizations",
        sa.Column("slug", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False))
    op.bulk_insert(organizations, [{"slug": "demo", "name": "Demonstration workspace"}])
    op.create_table("accounts",
        sa.Column("username", sa.String(120), primary_key=True),
        sa.Column("organization", sa.String(64), sa.ForeignKey("organizations.slug"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False))
    op.create_index("ix_accounts_organization", "accounts", ["organization"])
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("organization", sa.String(64), nullable=False, server_default="demo"))
        batch.add_column(sa.Column("owner", sa.String(120), nullable=False, server_default="reviewer"))
        batch.create_foreign_key("fk_cases_organization", "organizations", ["organization"], ["slug"])
        batch.create_index("ix_cases_organization", ["organization"])
    op.create_table("case_grants",
        sa.Column("case_id", sa.String(32), sa.ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("username", sa.String(120), sa.ForeignKey("accounts.username"), primary_key=True))

def downgrade():
    op.drop_table("case_grants")
    with op.batch_alter_table("cases") as batch:
        batch.drop_index("ix_cases_organization")
        batch.drop_constraint("fk_cases_organization", type_="foreignkey")
        batch.drop_column("owner")
        batch.drop_column("organization")
    op.drop_table("accounts")
    op.drop_table("organizations")
