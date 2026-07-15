"""add market-scoped saved reports

Revision ID: 20260606_0035
Revises: 20260606_0034
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0035"
down_revision: str | None = "20260606_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_reports",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False, server_default="tickets"),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("filters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("cadence", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("recipients", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_saved_report_market_name"),
    )
    op.create_index("ix_saved_reports_market_id", "saved_reports", ["market_id"])
    op.create_index("ix_saved_reports_cadence", "saved_reports", ["cadence"])
    op.create_index("ix_saved_reports_active", "saved_reports", ["active"])


def downgrade() -> None:
    op.drop_index("ix_saved_reports_active", table_name="saved_reports")
    op.drop_index("ix_saved_reports_cadence", table_name="saved_reports")
    op.drop_index("ix_saved_reports_market_id", table_name="saved_reports")
    op.drop_table("saved_reports")
