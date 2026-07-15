"""add support group team email

Revision ID: 20260605_0023
Revises: 20260604_0022
Create Date: 2026-06-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260605_0023"
down_revision: str | None = "20260604_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "support_groups",
        sa.Column("team_email", sa.String(length=255), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("support_groups", "team_email")
