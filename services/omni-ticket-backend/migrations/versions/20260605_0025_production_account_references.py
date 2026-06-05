"""add production account references

Revision ID: 20260605_0025
Revises: 20260605_0024
Create Date: 2026-06-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260605_0025"
down_revision: str | None = "20260605_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "production_account_references",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("area", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("account_name", sa.String(length=180), nullable=False),
        sa.Column("account_identifier", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="requested"),
        sa.Column("owner_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("credential_reference", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("docs_reference", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("callback_urls", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id",
            "provider",
            "account_name",
            name="uq_production_account_reference_market_provider_name",
        ),
    )
    op.create_index(
        "ix_production_account_references_market_id",
        "production_account_references",
        ["market_id"],
    )
    op.create_index(
        "ix_production_account_references_provider",
        "production_account_references",
        ["provider"],
    )
    op.create_index(
        "ix_production_account_references_status",
        "production_account_references",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_production_account_references_status", table_name="production_account_references")
    op.drop_index("ix_production_account_references_provider", table_name="production_account_references")
    op.drop_index("ix_production_account_references_market_id", table_name="production_account_references")
    op.drop_table("production_account_references")
