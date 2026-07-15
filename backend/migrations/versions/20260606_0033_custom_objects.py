"""add market-scoped custom objects

Revision ID: 20260606_0033
Revises: 20260606_0032
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0033"
down_revision: str | None = "20260606_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_objects",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("fields", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "key", name="uq_custom_object_market_key"),
    )
    op.create_index("ix_custom_objects_market_id", "custom_objects", ["market_id"])
    op.create_index("ix_custom_objects_active", "custom_objects", ["active"])


def downgrade() -> None:
    op.drop_index("ix_custom_objects_active", table_name="custom_objects")
    op.drop_index("ix_custom_objects_market_id", table_name="custom_objects")
    op.drop_table("custom_objects")
