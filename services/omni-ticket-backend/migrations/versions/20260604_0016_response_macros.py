"""add market-scoped response macros

Revision ID: 20260604_0016
Revises: 20260604_0015
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0016"
down_revision: str | None = "20260604_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "response_macros",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), server_default=""),
        sa.Column("language", sa.String(length=16), server_default="en"),
        sa.Column("channels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("shortcut", sa.String(length=80)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_response_macros_market_id", "response_macros", ["market_id"])
    op.create_index("ix_response_macros_active", "response_macros", ["active"])
    op.create_index("ix_response_macros_last_used_at", "response_macros", ["last_used_at"])


def downgrade() -> None:
    op.drop_index("ix_response_macros_last_used_at", table_name="response_macros")
    op.drop_index("ix_response_macros_active", table_name="response_macros")
    op.drop_index("ix_response_macros_market_id", table_name="response_macros")
    op.drop_table("response_macros")
