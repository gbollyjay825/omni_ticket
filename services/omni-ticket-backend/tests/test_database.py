from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.store import store
from app.db.bootstrap import create_schema, seed_reference_data, table_names
from app.db.models import (
    CustomerRecord,
    MarketRecord,
    ProductionAccountReferenceRecord,
    SlaPolicyRecord,
    SupportGroupRecord,
    TicketFieldRecord,
    TicketRecord,
    UserRecord,
)
from app.db.session import create_database_engine

ALEMBIC_HEAD = "20260606_0035"


def test_database_schema_and_seed_are_postgres_ready_with_local_sqlite(tmp_path: Path) -> None:
    database_path = tmp_path / "omni-ticket-test.db"
    engine = create_database_engine(f"sqlite:///{database_path}")

    create_schema(engine)
    tables = table_names(engine)

    assert "markets" in tables
    assert "users" in tables
    assert "tickets" in tables
    assert "ticket_fields" in tables
    assert "support_groups" in tables
    assert "sla_policies" in tables
    assert "business_hours" in tables
    assert "ticket_templates" in tables
    assert "tags" in tables
    assert "csat_surveys" in tables
    assert "email_notifications" in tables
    assert "scenario_automations" in tables
    assert "custom_field_definitions" in tables
    assert "custom_objects" in tables
    assert "products" in tables
    assert "saved_reports" in tables
    assert "customers" in tables
    assert "attachments" in tables
    assert "csat_feedback" in tables
    assert "connector_events" in tables
    assert "audit_events" in tables
    assert "analytics_rollups" in tables
    assert "operational_alerts" in tables
    assert "operational_alert_deliveries" in tables
    assert "email_provider_settings" in tables
    assert "integration_credential_settings" in tables
    assert "production_account_references" in tables
    assert "alembic_version" in tables

    with Session(engine) as session:
        seed_reference_data(session, store)
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

        markets = session.scalars(select(MarketRecord)).all()
        users = session.scalars(select(UserRecord)).all()
        nigeria_customers = session.scalars(
            select(CustomerRecord).where(CustomerRecord.market_id == "market-ng")
        ).all()
        ghana_tickets = session.scalars(
            select(TicketRecord).where(TicketRecord.market_id == "market-gh")
        ).all()
        ticket_fields = session.scalars(
            select(TicketFieldRecord).where(TicketFieldRecord.market_id == "market-ng")
        ).all()
        support_groups = session.scalars(
            select(SupportGroupRecord).where(SupportGroupRecord.market_id == "market-ng")
        ).all()
        sla_policies = session.scalars(
            select(SlaPolicyRecord).where(SlaPolicyRecord.market_id == "market-ng")
        ).all()
        account_references = session.scalars(select(ProductionAccountReferenceRecord)).all()

        assert {market.id for market in markets} >= {"market-ng", "market-gh", "market-uk"}
        assert any(user.email == "gbolahan@omniticket.example.com" for user in users)
        assert all(customer.market_id == "market-ng" for customer in nigeria_customers)
        assert len(ghana_tickets) == 1
        assert any(field.key == "booking_reference" for field in ticket_fields)
        assert any(group.name == "Billing Support" for group in support_groups)
        assert any(policy.priority == "urgent" for policy in sla_policies)
        assert account_references == []
        assert revision == ALEMBIC_HEAD


def test_create_schema_repairs_legacy_user_auth_columns_and_stamps_head(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "omni-ticket-legacy.db"
    engine = create_database_engine(f"sqlite:///{database_path}")

    with Session(engine) as session:
        session.execute(
            text(
                """
                CREATE TABLE users (
                    id VARCHAR(64) PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    role VARCHAR(32) NOT NULL,
                    market_ids JSON NOT NULL,
                    default_market_id VARCHAR(64) NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        session.execute(
            text(
                """
                INSERT INTO users (
                    id, email, name, role, market_ids, default_market_id, is_active, created_at, updated_at
                ) VALUES (
                    'legacy-user',
                    'legacy@example.com',
                    'Legacy User',
                    'admin',
                    '["market-ng"]',
                    'market-ng',
                    1,
                    '2026-05-30T00:00:00',
                    '2026-05-30T00:00:00'
                )
                """
            )
        )
        session.commit()

    create_schema(engine)

    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert {
        "password_hash",
        "password_reset_required",
        "mfa_enabled",
        "mfa_pending_secret",
        "mfa_secret",
        "mfa_confirmed_at",
        "mfa_last_verified_at",
        "permission_profile",
        "permission_overrides",
        "external_identity_provider",
        "external_subject",
        "external_last_login_at",
        "last_login_at",
    } <= user_columns
    assert "alembic_version" in inspector.get_table_names()
    assert "sla_policies" in inspector.get_table_names()
    assert "business_hours" in inspector.get_table_names()
    assert "ticket_templates" in inspector.get_table_names()
    assert "tags" in inspector.get_table_names()
    assert "csat_surveys" in inspector.get_table_names()
    assert "email_notifications" in inspector.get_table_names()
    assert "scenario_automations" in inspector.get_table_names()
    assert "custom_field_definitions" in inspector.get_table_names()
    assert "custom_objects" in inspector.get_table_names()
    assert "products" in inspector.get_table_names()
    assert "saved_reports" in inspector.get_table_names()

    with Session(engine) as session:
        user = session.execute(
            text(
                """
                    SELECT password_hash, password_reset_required, mfa_enabled,
                           permission_profile, permission_overrides, external_subject, last_login_at
                    FROM users
                    WHERE id = 'legacy-user'
                    """
            )
        ).one()
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert user.password_hash
    assert user.password_reset_required == 0
    assert user.mfa_enabled == 0
    assert user.permission_profile == "role_default"
    assert user.permission_overrides == "{}"
    assert user.external_subject is None
    assert user.last_login_at is None
    assert revision == ALEMBIC_HEAD


def test_create_schema_repairs_legacy_knowledge_review_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "omni-ticket-legacy-knowledge.db"
    engine = create_database_engine(f"sqlite:///{database_path}")

    with Session(engine) as session:
        session.execute(
            text(
                """
                CREATE TABLE knowledge_articles (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    language VARCHAR(32) NOT NULL,
                    market_ids JSON NOT NULL,
                    channels JSON NOT NULL,
                    tags JSON NOT NULL,
                    body TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        session.commit()

    create_schema(engine)

    inspector = inspect(engine)
    knowledge_columns = {column["name"] for column in inspector.get_columns("knowledge_articles")}
    assert {"submitted_for_review_at", "approved_at", "approved_by"} <= knowledge_columns
