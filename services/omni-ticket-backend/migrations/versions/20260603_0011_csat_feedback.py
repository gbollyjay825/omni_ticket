"""add csat feedback

Revision ID: 20260603_0011
Revises: 20260603_0010
Create Date: 2026-06-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260603_0011"
down_revision: str | None = "20260603_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "csat_feedback",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("submitted_by", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "ticket_id", name="uq_csat_market_ticket"),
    )
    op.create_index(op.f("ix_csat_feedback_customer_id"), "csat_feedback", ["customer_id"], unique=False)
    op.create_index(op.f("ix_csat_feedback_market_id"), "csat_feedback", ["market_id"], unique=False)
    op.create_index(op.f("ix_csat_feedback_source"), "csat_feedback", ["source"], unique=False)
    op.create_index(op.f("ix_csat_feedback_ticket_id"), "csat_feedback", ["ticket_id"], unique=False)
    op.add_column("analytics_rollups", sa.Column("avg_csat", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("analytics_rollups", "avg_csat")
    op.drop_index(op.f("ix_csat_feedback_ticket_id"), table_name="csat_feedback")
    op.drop_index(op.f("ix_csat_feedback_source"), table_name="csat_feedback")
    op.drop_index(op.f("ix_csat_feedback_market_id"), table_name="csat_feedback")
    op.drop_index(op.f("ix_csat_feedback_customer_id"), table_name="csat_feedback")
    op.drop_table("csat_feedback")
