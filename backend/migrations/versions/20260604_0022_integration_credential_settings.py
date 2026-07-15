"""add market integration credential settings

Revision ID: 20260604_0022
Revises: 20260604_0021
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0022"
down_revision: str | None = "20260604_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_credential_settings",
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("ai_provider", sa.String(length=32), nullable=False, server_default="auto"),
        sa.Column("anthropic_api_key", sa.Text(), nullable=True),
        sa.Column(
            "anthropic_api_base_url",
            sa.String(length=255),
            nullable=False,
            server_default="https://api.anthropic.com",
        ),
        sa.Column(
            "anthropic_model",
            sa.String(length=120),
            nullable=False,
            server_default="claude-sonnet-4-6",
        ),
        sa.Column("alert_webhook_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("alert_webhook_secret", sa.Text(), nullable=True),
        sa.Column(
            "alert_delivery_min_severity",
            sa.String(length=32),
            nullable=False,
            server_default="warning",
        ),
        sa.Column("sms_http_endpoint", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("sms_http_auth_token", sa.Text(), nullable=True),
        sa.Column("sms_http_from", sa.String(length=120), nullable=False, server_default=""),
        sa.Column(
            "sms_http_auth_header",
            sa.String(length=120),
            nullable=False,
            server_default="Authorization",
        ),
        sa.Column(
            "sms_http_auth_scheme",
            sa.String(length=80),
            nullable=False,
            server_default="Bearer",
        ),
        sa.Column(
            "sms_http_delivery_callback_url",
            sa.String(length=500),
            nullable=False,
            server_default="",
        ),
        sa.Column("voice_http_endpoint", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("voice_http_auth_token", sa.Text(), nullable=True),
        sa.Column("voice_http_from", sa.String(length=120), nullable=False, server_default=""),
        sa.Column(
            "voice_http_auth_header",
            sa.String(length=120),
            nullable=False,
            server_default="Authorization",
        ),
        sa.Column(
            "voice_http_auth_scheme",
            sa.String(length=80),
            nullable=False,
            server_default="Bearer",
        ),
        sa.Column(
            "voice_http_status_callback_url",
            sa.String(length=500),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "whatsapp_cloud_api_base_url",
            sa.String(length=255),
            nullable=False,
            server_default="https://graph.facebook.com/v25.0",
        ),
        sa.Column(
            "whatsapp_phone_number_id",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("whatsapp_access_token", sa.Text(), nullable=True),
        sa.Column("whatsapp_preview_urls", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "facebook_graph_api_base_url",
            sa.String(length=255),
            nullable=False,
            server_default="https://graph.facebook.com/v25.0",
        ),
        sa.Column("facebook_page_id", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("facebook_page_access_token", sa.Text(), nullable=True),
        sa.Column(
            "facebook_messaging_type",
            sa.String(length=40),
            nullable=False,
            server_default="RESPONSE",
        ),
        sa.Column(
            "instagram_graph_api_base_url",
            sa.String(length=255),
            nullable=False,
            server_default="https://graph.instagram.com/v25.0",
        ),
        sa.Column(
            "instagram_business_account_id",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("instagram_access_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("market_id"),
    )


def downgrade() -> None:
    op.drop_table("integration_credential_settings")
