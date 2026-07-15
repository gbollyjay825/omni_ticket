"""add market-scoped scenario automations

Revision ID: 20260606_0031
Revises: 20260606_0030
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0031"
down_revision: str | None = "20260606_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenario_automations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("actions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_scenario_automation_market_name"),
    )
    op.create_index("ix_scenario_automations_market_id", "scenario_automations", ["market_id"])
    op.create_index("ix_scenario_automations_active", "scenario_automations", ["active"])


def downgrade() -> None:
    op.drop_index("ix_scenario_automations_active", table_name="scenario_automations")
    op.drop_index("ix_scenario_automations_market_id", table_name="scenario_automations")
    op.drop_table("scenario_automations")
