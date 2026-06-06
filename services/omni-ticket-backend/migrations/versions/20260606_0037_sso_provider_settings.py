"""add global SSO/OIDC provider settings (editable enterprise SSO credentials)

Revision ID: 20260606_0037
Revises: 20260606_0036
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0037"
down_revision: str | None = "20260606_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sso_provider_settings",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "provider_name",
            sa.String(length=120),
            nullable=False,
            server_default="Enterprise SSO",
        ),
        sa.Column("issuer_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("authorization_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("token_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("userinfo_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("client_id", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("client_secret", sa.Text(), nullable=True),
        sa.Column("redirect_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("allowed_email_domains", sa.JSON(), nullable=False),
        sa.Column(
            "auto_provision_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("default_role", sa.String(length=32), nullable=False, server_default="agent"),
        sa.Column("default_market_id", sa.String(length=64), nullable=True),
        sa.Column(
            "require_email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sso_provider_settings")
