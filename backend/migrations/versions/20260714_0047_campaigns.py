"""add proactive campaign drafts

Revision ID: 20260714_0047
Revises: 20260714_0046
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0047"
down_revision: str | None = "20260714_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column("audience", sa.JSON(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_campaign_market_name"),
    )
    op.create_index("ix_campaigns_market_id", "campaigns", ["market_id"])
    op.create_index("ix_campaigns_channel", "campaigns", ["channel"])
    op.create_index("ix_campaigns_status", "campaigns", ["status"])
    op.create_index("ix_campaigns_scheduled_at", "campaigns", ["scheduled_at"])


def downgrade() -> None:
    op.drop_index("ix_campaigns_scheduled_at", table_name="campaigns")
    op.drop_index("ix_campaigns_status", table_name="campaigns")
    op.drop_index("ix_campaigns_channel", table_name="campaigns")
    op.drop_index("ix_campaigns_market_id", table_name="campaigns")
    op.drop_table("campaigns")
