"""add embeddable chat widget settings (per market)

Revision ID: 20260607_0040
Revises: 20260607_0039
Create Date: 2026-06-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260607_0040"
down_revision: str | None = "20260607_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "widget_settings",
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("display_name", sa.String(length=120), nullable=False, server_default="Chat with us"),
        sa.Column(
            "welcome_message",
            sa.Text(),
            nullable=False,
            server_default="Hi! How can we help you today?",
        ),
        sa.Column("primary_color", sa.String(length=20), nullable=False, server_default="#0b5eea"),
        sa.Column("launcher_label", sa.String(length=80), nullable=False, server_default="Support"),
        sa.Column("position", sa.String(length=20), nullable=False, server_default="bottom-right"),
        sa.Column("auto_open_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("collect_email", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("offline_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("market_id"),
    )


def downgrade() -> None:
    op.drop_table("widget_settings")
