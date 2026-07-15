"""Add durable ticket saved views.

Revision ID: 20260714_0054
Revises: 20260714_0053
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_0054"
down_revision = "20260714_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_views",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64)),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("sort_by", sa.String(length=40), nullable=False, server_default="updated_at"),
        sa.Column("sort_order", sa.String(length=8), nullable=False, server_default="desc"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "owner_user_id", "name", name="uq_ticket_view_owner_name"),
    )
    for column in ("market_id", "owner_user_id", "active"):
        op.create_index(f"ix_ticket_views_{column}", "ticket_views", [column])


def downgrade() -> None:
    op.drop_table("ticket_views")
