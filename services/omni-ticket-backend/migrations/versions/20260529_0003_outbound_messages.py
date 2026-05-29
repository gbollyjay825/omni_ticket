"""add outbound message queue

Revision ID: 20260529_0003
Revises: 20260527_0002
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260529_0003"
down_revision: str | None = "20260527_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbound_messages",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("ticket_id", sa.String(length=64), sa.ForeignKey("tickets.id")),
        sa.Column("timeline_event_id", sa.String(length=64), sa.ForeignKey("timeline_events.id")),
        sa.Column("connector_event_id", sa.String(length=64), sa.ForeignKey("connector_events.id")),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("actor", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("market_id", "provider", "idempotency_key", name="uq_outbound_market_provider_key"),
    )
    op.create_index("ix_outbound_messages_market_id", "outbound_messages", ["market_id"])
    op.create_index("ix_outbound_messages_ticket_id", "outbound_messages", ["ticket_id"])
    op.create_index("ix_outbound_messages_provider", "outbound_messages", ["provider"])
    op.create_index("ix_outbound_messages_status", "outbound_messages", ["status"])


def downgrade() -> None:
    op.drop_table("outbound_messages")
