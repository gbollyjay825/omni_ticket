"""add AI agent studio records

Revision ID: 20260714_0049
Revises: 20260714_0048
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0049"
down_revision: str | None = "20260714_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("handoff_team", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("confidence_threshold", sa.Integer(), nullable=False, server_default="75"),
        sa.Column("auto_send", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_ai_agent_market_name"),
    )
    op.create_index("ix_ai_agents_market_id", "ai_agents", ["market_id"])
    op.create_index("ix_ai_agents_status", "ai_agents", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ai_agents_status", table_name="ai_agents")
    op.drop_index("ix_ai_agents_market_id", table_name="ai_agents")
    op.drop_table("ai_agents")
