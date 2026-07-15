"""add market-scoped products

Revision ID: 20260606_0034
Revises: 20260606_0033
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0034"
down_revision: str | None = "20260606_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_product_market_name"),
    )
    op.create_index("ix_products_market_id", "products", ["market_id"])
    op.create_index("ix_products_active", "products", ["active"])


def downgrade() -> None:
    op.drop_index("ix_products_active", table_name="products")
    op.drop_index("ix_products_market_id", table_name="products")
    op.drop_table("products")
