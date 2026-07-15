"""add market-scoped sla policies

Revision ID: 20260604_0019
Revises: 20260604_0018
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0019"
down_revision: str | None = "20260604_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sla_policies",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("channels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("first_response_minutes", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column(
            "business_hours",
            sa.String(length=120),
            nullable=False,
            server_default="Business hours",
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_sla_policy_market_name"),
    )
    op.create_index("ix_sla_policies_market_id", "sla_policies", ["market_id"])
    op.create_index("ix_sla_policies_active", "sla_policies", ["active"])
    op.create_index("ix_sla_policies_priority", "sla_policies", ["priority"])


def downgrade() -> None:
    op.drop_index("ix_sla_policies_priority", table_name="sla_policies")
    op.drop_index("ix_sla_policies_active", table_name="sla_policies")
    op.drop_index("ix_sla_policies_market_id", table_name="sla_policies")
    op.drop_table("sla_policies")
