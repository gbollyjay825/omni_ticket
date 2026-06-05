"""add operational alerts

Revision ID: 20260603_0008
Revises: 20260530_0007
Create Date: 2026-06-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260603_0008"
down_revision: str | None = "20260530_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_alerts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=180), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "dedupe_key", name="uq_operational_alert_market_dedupe"),
    )
    op.create_index(
        op.f("ix_operational_alerts_market_id"),
        "operational_alerts",
        ["market_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_alerts_severity"),
        "operational_alerts",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_alerts_source"),
        "operational_alerts",
        ["source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_alerts_status"),
        "operational_alerts",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_operational_alerts_status"), table_name="operational_alerts")
    op.drop_index(op.f("ix_operational_alerts_source"), table_name="operational_alerts")
    op.drop_index(op.f("ix_operational_alerts_severity"), table_name="operational_alerts")
    op.drop_index(op.f("ix_operational_alerts_market_id"), table_name="operational_alerts")
    op.drop_table("operational_alerts")
