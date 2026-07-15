"""add market-scoped ticket templates

Revision ID: 20260606_0027
Revises: 20260605_0026
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0027"
down_revision: str | None = "20260605_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_templates",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="email"),
        sa.Column("group", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_ticket_template_market_name"),
    )
    op.create_index("ix_ticket_templates_market_id", "ticket_templates", ["market_id"])
    op.create_index("ix_ticket_templates_active", "ticket_templates", ["active"])


def downgrade() -> None:
    op.drop_index("ix_ticket_templates_active", table_name="ticket_templates")
    op.drop_index("ix_ticket_templates_market_id", table_name="ticket_templates")
    op.drop_table("ticket_templates")
