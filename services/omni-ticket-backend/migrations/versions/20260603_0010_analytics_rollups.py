"""add analytics rollups

Revision ID: 20260603_0010
Revises: 20260603_0009
Create Date: 2026-06-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260603_0010"
down_revision: str | None = "20260603_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_rollups",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_tickets", sa.Integer(), nullable=False),
        sa.Column("at_risk_tickets", sa.Integer(), nullable=False),
        sa.Column("breached_tickets", sa.Integer(), nullable=False),
        sa.Column("active_agents", sa.Integer(), nullable=False),
        sa.Column("avg_occupancy", sa.Integer(), nullable=False),
        sa.Column("channel_volume", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "period_start", name="uq_analytics_rollup_market_period"),
    )
    op.create_index(
        op.f("ix_analytics_rollups_market_id"),
        "analytics_rollups",
        ["market_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_rollups_period_end"),
        "analytics_rollups",
        ["period_end"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_rollups_period_start"),
        "analytics_rollups",
        ["period_start"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analytics_rollups_period_start"), table_name="analytics_rollups")
    op.drop_index(op.f("ix_analytics_rollups_period_end"), table_name="analytics_rollups")
    op.drop_index(op.f("ix_analytics_rollups_market_id"), table_name="analytics_rollups")
    op.drop_table("analytics_rollups")
