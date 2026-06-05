"""add linked ticket to handoffs

Revision ID: 20260605_0024
Revises: 20260605_0023
Create Date: 2026-06-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260605_0024"
down_revision: str | None = "20260605_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("handoffs", sa.Column("linked_ticket_id", sa.String(length=64), nullable=True))
    op.create_index("ix_handoffs_linked_ticket_id", "handoffs", ["linked_ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_handoffs_linked_ticket_id", table_name="handoffs")
    op.drop_column("handoffs", "linked_ticket_id")
