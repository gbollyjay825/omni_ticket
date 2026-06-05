"""add user mfa fields

Revision ID: 20260604_0012
Revises: 20260603_0011
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0012"
down_revision: str | None = "20260603_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("users", sa.Column("mfa_pending_secret", sa.String(length=96), nullable=True))
    op.add_column("users", sa.Column("mfa_secret", sa.String(length=96), nullable=True))
    op.add_column("users", sa.Column("mfa_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("mfa_last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "mfa_last_verified_at")
    op.drop_column("users", "mfa_confirmed_at")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "mfa_pending_secret")
    op.drop_column("users", "mfa_enabled")
