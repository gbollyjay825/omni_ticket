"""add connector accounts

Revision ID: 20260527_0002
Revises: 20260527_0001
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0002"
down_revision: str | None = "20260527_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_accounts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("account_identifier", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("intake_enabled", sa.Boolean(), nullable=False),
        sa.Column("outbound_enabled", sa.Boolean(), nullable=False),
        sa.Column("webhook_url", sa.String(length=500), nullable=False),
        sa.Column("webhook_verified", sa.Boolean(), nullable=False),
        sa.Column("credential_ref", sa.String(length=255)),
        sa.Column("secret_configured", sa.Boolean(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("required_credentials", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("market_id", "provider", name="uq_connector_account_market_provider"),
    )
    op.create_index("ix_connector_accounts_market_id", "connector_accounts", ["market_id"])
    op.create_index("ix_connector_accounts_provider", "connector_accounts", ["provider"])


def downgrade() -> None:
    op.drop_table("connector_accounts")
