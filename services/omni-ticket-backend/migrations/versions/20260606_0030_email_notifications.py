"""add market-scoped email notification rules

Revision ID: 20260606_0030
Revises: 20260606_0029
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0030"
down_revision: str | None = "20260606_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_notifications",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("event", sa.String(length=80), nullable=False, server_default="ticket_created"),
        sa.Column("recipients", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("subject", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_email_notification_market_name"),
    )
    op.create_index("ix_email_notifications_market_id", "email_notifications", ["market_id"])
    op.create_index("ix_email_notifications_event", "email_notifications", ["event"])
    op.create_index("ix_email_notifications_active", "email_notifications", ["active"])


def downgrade() -> None:
    op.drop_index("ix_email_notifications_active", table_name="email_notifications")
    op.drop_index("ix_email_notifications_event", table_name="email_notifications")
    op.drop_index("ix_email_notifications_market_id", table_name="email_notifications")
    op.drop_table("email_notifications")
