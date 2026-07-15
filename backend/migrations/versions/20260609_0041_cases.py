"""add cases (group tickets across channels for one customer)

Revision ID: 20260609_0041
Revises: 20260607_0040
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260609_0041"
down_revision: str | None = "20260607_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("opened_by", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cases_market_id", "cases", ["market_id"])
    op.create_index("ix_cases_customer_id", "cases", ["customer_id"])
    op.create_index("ix_cases_public_id", "cases", ["public_id"])
    op.create_index("ix_cases_status", "cases", ["status"])

    # Each ticket may belong to at most one case (nullable — most tickets stand alone).
    op.add_column("tickets", sa.Column("case_id", sa.String(length=64), nullable=True))
    op.create_index("ix_tickets_case_id", "tickets", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_tickets_case_id", table_name="tickets")
    op.drop_column("tickets", "case_id")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_public_id", table_name="cases")
    op.drop_index("ix_cases_customer_id", table_name="cases")
    op.drop_index("ix_cases_market_id", table_name="cases")
    op.drop_table("cases")
