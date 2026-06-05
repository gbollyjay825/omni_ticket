"""add market-scoped ticket fields

Revision ID: 20260604_0017
Revises: 20260604_0016
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0017"
down_revision: str | None = "20260604_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("custom_fields", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "ticket_fields",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("field_type", sa.String(length=32), server_default="text"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("options", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("channels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("placeholder", sa.String(length=255), server_default=""),
        sa.Column("help_text", sa.Text(), server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "key", name="uq_ticket_field_market_key"),
    )
    op.create_index("ix_ticket_fields_market_id", "ticket_fields", ["market_id"])
    op.create_index("ix_ticket_fields_active", "ticket_fields", ["active"])
    op.create_index("ix_ticket_fields_position", "ticket_fields", ["position"])


def downgrade() -> None:
    op.drop_index("ix_ticket_fields_position", table_name="ticket_fields")
    op.drop_index("ix_ticket_fields_active", table_name="ticket_fields")
    op.drop_index("ix_ticket_fields_market_id", table_name="ticket_fields")
    op.drop_table("ticket_fields")
    op.drop_column("tickets", "custom_fields")
