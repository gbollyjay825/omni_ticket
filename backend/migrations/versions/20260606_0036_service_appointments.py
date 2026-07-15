"""add market-scoped service appointments (field service scheduling)

Revision ID: 20260606_0036
Revises: 20260606_0035
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0036"
down_revision: str | None = "20260606_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_appointments",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("technician_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled"),
        sa.Column("location", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_service_appointments_market_id", "service_appointments", ["market_id"])
    op.create_index("ix_service_appointments_technician_id", "service_appointments", ["technician_id"])
    op.create_index("ix_service_appointments_scheduled_at", "service_appointments", ["scheduled_at"])
    op.create_index("ix_service_appointments_status", "service_appointments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_service_appointments_status", table_name="service_appointments")
    op.drop_index("ix_service_appointments_scheduled_at", table_name="service_appointments")
    op.drop_index("ix_service_appointments_technician_id", table_name="service_appointments")
    op.drop_index("ix_service_appointments_market_id", table_name="service_appointments")
    op.drop_table("service_appointments")
