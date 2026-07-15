"""add durable scheduled report deliveries

Revision ID: 20260714_0046
Revises: 20260714_0045
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0046"
down_revision: str | None = "20260714_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_deliveries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("saved_report_id", sa.String(length=64), nullable=False),
        sa.Column("period_key", sa.String(length=32), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("cadence", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False, server_default="text/csv"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_checksum", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["saved_report_id"], ["saved_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "saved_report_id",
            "period_key",
            name="uq_report_delivery_report_period",
        ),
    )
    op.create_index("ix_report_deliveries_market_id", "report_deliveries", ["market_id"])
    op.create_index(
        "ix_report_deliveries_saved_report_id",
        "report_deliveries",
        ["saved_report_id"],
    )
    op.create_index("ix_report_deliveries_period_key", "report_deliveries", ["period_key"])
    op.create_index("ix_report_deliveries_report_type", "report_deliveries", ["report_type"])
    op.create_index("ix_report_deliveries_cadence", "report_deliveries", ["cadence"])
    op.create_index("ix_report_deliveries_status", "report_deliveries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_report_deliveries_status", table_name="report_deliveries")
    op.drop_index("ix_report_deliveries_cadence", table_name="report_deliveries")
    op.drop_index("ix_report_deliveries_report_type", table_name="report_deliveries")
    op.drop_index("ix_report_deliveries_period_key", table_name="report_deliveries")
    op.drop_index("ix_report_deliveries_saved_report_id", table_name="report_deliveries")
    op.drop_index("ix_report_deliveries_market_id", table_name="report_deliveries")
    op.drop_table("report_deliveries")
