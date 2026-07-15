"""add operational alert deliveries

Revision ID: 20260603_0009
Revises: 20260603_0008
Create Date: 2026-06-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260603_0009"
down_revision: str | None = "20260603_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_alert_deliveries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("alert_id", sa.String(length=64), nullable=False),
        sa.Column("destination_type", sa.String(length=64), nullable=False),
        sa.Column("destination_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["operational_alerts.id"]),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "alert_id",
            "destination_type",
            "destination_name",
            name="uq_alert_delivery_destination",
        ),
    )
    op.create_index(
        op.f("ix_operational_alert_deliveries_alert_id"),
        "operational_alert_deliveries",
        ["alert_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_alert_deliveries_destination_type"),
        "operational_alert_deliveries",
        ["destination_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_alert_deliveries_market_id"),
        "operational_alert_deliveries",
        ["market_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_alert_deliveries_status"),
        "operational_alert_deliveries",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_operational_alert_deliveries_status"), table_name="operational_alert_deliveries")
    op.drop_index(op.f("ix_operational_alert_deliveries_market_id"), table_name="operational_alert_deliveries")
    op.drop_index(
        op.f("ix_operational_alert_deliveries_destination_type"),
        table_name="operational_alert_deliveries",
    )
    op.drop_index(op.f("ix_operational_alert_deliveries_alert_id"), table_name="operational_alert_deliveries")
    op.drop_table("operational_alert_deliveries")
