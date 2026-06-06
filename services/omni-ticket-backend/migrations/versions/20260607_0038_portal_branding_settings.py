"""add portal/helpdesk branding columns to workspace settings

Revision ID: 20260607_0038
Revises: 20260606_0037
Create Date: 2026-06-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260607_0038"
down_revision: str | None = "20260606_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace_settings",
        sa.Column("portal_logo_url", sa.String(length=500), nullable=False, server_default=""),
    )
    op.add_column(
        "workspace_settings",
        sa.Column(
            "portal_primary_color",
            sa.String(length=20),
            nullable=False,
            server_default="#0b5eea",
        ),
    )
    op.add_column(
        "workspace_settings",
        sa.Column("portal_support_name", sa.String(length=160), nullable=False, server_default=""),
    )
    op.add_column(
        "workspace_settings",
        sa.Column("portal_welcome_message", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("workspace_settings", "portal_welcome_message")
    op.drop_column("workspace_settings", "portal_support_name")
    op.drop_column("workspace_settings", "portal_primary_color")
    op.drop_column("workspace_settings", "portal_logo_url")
