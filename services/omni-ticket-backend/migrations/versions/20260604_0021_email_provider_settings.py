"""add market email provider settings

Revision ID: 20260604_0021
Revises: 20260604_0020
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0021"
down_revision: str | None = "20260604_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_provider_settings",
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("inbound_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("inbound_host", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("inbound_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("inbound_username", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("inbound_password", sa.Text(), nullable=True),
        sa.Column("inbound_mailbox", sa.String(length=120), nullable=False, server_default="INBOX"),
        sa.Column("inbound_use_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("inbound_mark_seen", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("outbound_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("outbound_host", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("outbound_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("outbound_username", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("outbound_password", sa.Text(), nullable=True),
        sa.Column("outbound_from_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("outbound_use_starttls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("outbound_use_ssl", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("market_id"),
    )


def downgrade() -> None:
    op.drop_table("email_provider_settings")
