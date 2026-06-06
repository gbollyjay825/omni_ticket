"""add market-scoped tags

Revision ID: 20260606_0028
Revises: 20260606_0027
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0028"
down_revision: str | None = "20260606_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=9), nullable=False, server_default="#2f6fed"),
        sa.Column("description", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_tag_market_name"),
    )
    op.create_index("ix_tags_market_id", "tags", ["market_id"])
    op.create_index("ix_tags_active", "tags", ["active"])


def downgrade() -> None:
    op.drop_index("ix_tags_active", table_name="tags")
    op.drop_index("ix_tags_market_id", table_name="tags")
    op.drop_table("tags")
