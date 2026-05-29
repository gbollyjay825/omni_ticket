"""initial platform schema

Revision ID: 20260527_0001
Revises:
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260527_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("code", sa.String(length=16), nullable=False, unique=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("default_locale", sa.String(length=16), nullable=False),
        sa.Column("support_email", sa.String(length=255), nullable=False),
        sa.Column("whatsapp_number", sa.String(length=64)),
        sa.Column("facebook_page", sa.String(length=160)),
        sa.Column("instagram_handle", sa.String(length=160)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_markets_code", "markets", ["code"])

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("default_market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("market_ids", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_default_market_id", "users", ["default_market_id"])

    op.create_table(
        "workspace_settings",
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id"), primary_key=True),
        sa.Column("ai_work_queue_automation_enabled", sa.Boolean(), nullable=False),
        sa.Column("ai_can_send_customer_messages", sa.Boolean(), nullable=False),
        sa.Column("default_timezone", sa.String(length=80), nullable=False),
        sa.Column("business_hours", sa.String(length=120), nullable=False),
        sa.Column("public_brand_name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("token", sa.String(length=128), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("occupancy", sa.Integer(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("market_ids", sa.JSON(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agents_email", "agents", ["email"])

    op.create_table(
        "channels",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("handle", sa.String(length=255), nullable=False),
        sa.Column("health", sa.String(length=32), nullable=False),
        sa.Column("queued", sa.Integer(), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False),
        sa.Column("sla_risk", sa.Integer(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_channels_market_id", "channels", ["market_id"])
    op.create_index("ix_channels_type", "channels", ["type"])

    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("tier", sa.String(length=40), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("account_value", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_companies_market_id", "companies", ["market_id"])

    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("company_id", sa.String(length=64), sa.ForeignKey("companies.id")),
        sa.Column("location", sa.String(length=180), nullable=False),
        sa.Column("sentiment", sa.String(length=32), nullable=False),
        sa.Column("preferred_channels", sa.JSON(), nullable=False),
        sa.Column("contact_points", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("market_id", "email", name="uq_customer_market_email"),
    )
    op.create_index("ix_customers_market_id", "customers", ["market_id"])
    op.create_index("ix_customers_email", "customers", ["email"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.String(length=64), sa.ForeignKey("customers.id")),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("sentiment", sa.String(length=32), nullable=False),
        sa.Column("assignee_id", sa.String(length=64)),
        sa.Column("team", sa.String(length=120), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("tasks", sa.JSON(), nullable=False),
        sa.Column("sla", sa.JSON(), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tickets_market_id", "tickets", ["market_id"])
    op.create_index("ix_tickets_public_id", "tickets", ["public_id"])
    op.create_index("ix_tickets_customer_id", "tickets", ["customer_id"])
    op.create_index("ix_tickets_channel", "tickets", ["channel"])
    op.create_index("ix_tickets_assignee_id", "tickets", ["assignee_id"])

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("ticket_id", sa.String(length=64), sa.ForeignKey("tickets.id")),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("public", sa.Boolean(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_timeline_events_market_id", "timeline_events", ["market_id"])
    op.create_index("ix_timeline_events_ticket_id", "timeline_events", ["ticket_id"])

    op.create_table(
        "handoffs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("ticket_id", sa.String(length=64), sa.ForeignKey("tickets.id")),
        sa.Column("from_team", sa.String(length=120), nullable=False),
        sa.Column("to_team", sa.String(length=120), nullable=False),
        sa.Column("requested_by", sa.String(length=180), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("blocker", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_handoffs_market_id", "handoffs", ["market_id"])
    op.create_index("ix_handoffs_ticket_id", "handoffs", ["ticket_id"])

    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("market_ids", sa.JSON(), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "automation_rules",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("last_fired_at", sa.DateTime(timezone=True)),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_automation_rules_market_id", "automation_rules", ["market_id"])

    op.create_table(
        "connector_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=180), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), sa.ForeignKey("tickets.id")),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("market_id", "provider", "external_id", name="uq_connector_market_event"),
    )
    op.create_index("ix_connector_events_market_id", "connector_events", ["market_id"])
    op.create_index("ix_connector_events_provider", "connector_events", ["provider"])
    op.create_index("ix_connector_events_external_id", "connector_events", ["external_id"])

    op.create_table(
        "ai_decisions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("ticket_id", sa.String(length=64), sa.ForeignKey("tickets.id")),
        sa.Column("decision_type", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("input_reference", sa.String(length=180), nullable=False),
        sa.Column("override_allowed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_decisions_market_id", "ai_decisions", ["market_id"])
    op.create_index("ix_ai_decisions_ticket_id", "ai_decisions", ["ticket_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("market_id", sa.String(length=64), sa.ForeignKey("markets.id")),
        sa.Column("actor", sa.String(length=180), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_market_id", "audit_events", ["market_id"])


def downgrade() -> None:
    for table_name in [
        "audit_events",
        "ai_decisions",
        "connector_events",
        "automation_rules",
        "knowledge_articles",
        "handoffs",
        "timeline_events",
        "tickets",
        "customers",
        "companies",
        "channels",
        "agents",
        "sessions",
        "workspace_settings",
        "users",
        "markets",
    ]:
        op.drop_table(table_name)
