"""add consented proactive campaign deliveries

Revision ID: 20260714_0050
Revises: 20260714_0049
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0050"
down_revision: str | None = "20260714_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("template_name", sa.String(length=180), nullable=False, server_default=""),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "template_language", sa.String(length=20), nullable=False, server_default="en_US"
        ),
    )
    op.add_column(
        "campaigns",
        sa.Column("template_variables", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("campaigns", sa.Column("launched_at", sa.DateTime(timezone=True)))
    op.add_column("campaigns", sa.Column("completed_at", sa.DateTime(timezone=True)))

    op.create_table(
        "campaign_consents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("evidence", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("captured_by", sa.String(length=180), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_id",
            "customer_id",
            "channel",
            name="uq_campaign_consent_market_customer_channel",
        ),
    )
    op.create_index("ix_campaign_consents_market_id", "campaign_consents", ["market_id"])
    op.create_index("ix_campaign_consents_customer_id", "campaign_consents", ["customer_id"])
    op.create_index("ix_campaign_consents_channel", "campaign_consents", ["channel"])
    op.create_index("ix_campaign_consents_status", "campaign_consents", ["status"])

    op.create_table(
        "campaign_deliveries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("consent_id", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("external_id", sa.String(length=255)),
        sa.Column("last_error", sa.Text()),
        sa.Column("provider_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["consent_id"], ["campaign_consents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id", "customer_id", name="uq_campaign_delivery_campaign_customer"
        ),
        sa.UniqueConstraint(
            "market_id",
            "channel",
            "idempotency_key",
            name="uq_campaign_delivery_market_channel_key",
        ),
    )
    for column in (
        "campaign_id",
        "market_id",
        "customer_id",
        "consent_id",
        "channel",
        "status",
        "next_attempt_at",
        "external_id",
    ):
        op.create_index(f"ix_campaign_deliveries_{column}", "campaign_deliveries", [column])


def downgrade() -> None:
    op.drop_table("campaign_deliveries")
    op.drop_table("campaign_consents")
    op.drop_column("campaigns", "completed_at")
    op.drop_column("campaigns", "launched_at")
    op.drop_column("campaigns", "template_variables")
    op.drop_column("campaigns", "template_language")
    op.drop_column("campaigns", "template_name")
