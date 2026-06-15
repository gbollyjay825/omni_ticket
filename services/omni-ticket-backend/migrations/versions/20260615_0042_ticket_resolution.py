"""add ticket resolution lifecycle columns (resolved_at, closed_at, frozen SLA outcome)

Revision ID: 20260615_0042
Revises: 20260609_0041
Create Date: 2026-06-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260615_0042"
down_revision: str | None = "20260609_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # When a ticket is resolved/closed we stamp the moment and freeze whether it
    # met SLA at that instant, so later wall-clock drift can't flip the outcome.
    op.add_column("tickets", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("sla_resolution_met", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("tickets", "sla_resolution_met")
    op.drop_column("tickets", "closed_at")
    op.drop_column("tickets", "resolved_at")
