"""add user permission profiles

Revision ID: 20260604_0013
Revises: 20260604_0012
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0013"
down_revision: str | None = "20260604_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "permission_profile",
            sa.String(length=40),
            nullable=False,
            server_default="role_default",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "permission_overrides",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "permission_overrides")
    op.drop_column("users", "permission_profile")
