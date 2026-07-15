"""add ticket attachment metadata

Revision ID: 20260529_0006
Revises: 20260529_0005
Create Date: 2026-05-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260529_0006"
down_revision: str | None = "20260529_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column(
            "timeline_event_id",
            sa.String(length=64),
            sa.ForeignKey("timeline_events.id"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=160),
            nullable=False,
            server_default="application/octet-stream",
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by", sa.String(length=180), nullable=False),
        sa.Column("scan_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("scan_result", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_attachments_market_id", "attachments", ["market_id"])
    op.create_index("ix_attachments_ticket_id", "attachments", ["ticket_id"])
    op.create_index("ix_attachments_scan_status", "attachments", ["scan_status"])


def downgrade() -> None:
    op.drop_index("ix_attachments_scan_status", table_name="attachments")
    op.drop_index("ix_attachments_ticket_id", table_name="attachments")
    op.drop_index("ix_attachments_market_id", table_name="attachments")
    op.drop_table("attachments")
