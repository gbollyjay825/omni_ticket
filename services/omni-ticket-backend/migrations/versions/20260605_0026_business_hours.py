"""add market-scoped business hours

Revision ID: 20260605_0026
Revises: 20260605_0025
Create Date: 2026-06-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260605_0026"
down_revision: str | None = "20260605_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_hours",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Africa/Lagos"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("days", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_business_hours_market_name"),
    )
    op.create_index("ix_business_hours_market_id", "business_hours", ["market_id"])
    op.create_index("ix_business_hours_active", "business_hours", ["active"])


def downgrade() -> None:
    op.drop_index("ix_business_hours_active", table_name="business_hours")
    op.drop_index("ix_business_hours_market_id", table_name="business_hours")
    op.drop_table("business_hours")
