"""add market-scoped support groups

Revision ID: 20260604_0018
Revises: 20260604_0017
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0018"
down_revision: str | None = "20260604_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_groups",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("channels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_support_group_market_name"),
    )
    op.create_index("ix_support_groups_market_id", "support_groups", ["market_id"])
    op.create_index("ix_support_groups_active", "support_groups", ["active"])


def downgrade() -> None:
    op.drop_index("ix_support_groups_active", table_name="support_groups")
    op.drop_index("ix_support_groups_market_id", table_name="support_groups")
    op.drop_table("support_groups")
