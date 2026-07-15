from pathlib import Path
from secrets import token_urlsafe

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore, store
from app.core.config import settings
from app.core.passwords import hash_password, verify_password
from app.db.models import (
    AgentRecord,
    AiDecisionRecord,
    AuditEventRecord,
    AutomationRuleRecord,
    Base,
    BusinessHoursRecord,
    ChannelRecord,
    ConnectorAccountRecord,
    CompanyRecord,
    CaseRecord,
    CsatSurveyRecord,
    CustomFieldDefinitionRecord,
    CustomObjectRecord,
    DiscussionCommentRecord,
    DiscussionTopicRecord,
    EmailNotificationRecord,
    ProductRecord,
    SavedReportRecord,
    ServiceAppointmentRecord,
    ScenarioAutomationRecord,
    ConnectorEventRecord,
    CustomerRecord,
    HandoffRecord,
    KnowledgeArticleRecord,
    MarketRecord,
    ResponseMacroRecord,
    SlaPolicyRecord,
    SupportGroupRecord,
    TagRecord,
    TicketFieldRecord,
    TicketRecord,
    TicketTemplateRecord,
    TimelineEventRecord,
    UserRecord,
    WorkspaceSettingsRecord,
)
from app.db.session import get_engine
from app.db.store_sync import hydrate_store_state


def _payload(model: object) -> dict:
    data = model.model_dump(mode="json")  # type: ignore[attr-defined]
    data.pop("created_at", None)
    data.pop("updated_at", None)
    return data


def _alembic_head_revision() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    versions_dir = repo_root / "migrations" / "versions"
    revisions: list[str] = []
    for path in versions_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        revision = path.stem.split("_", 2)
        if len(revision) >= 2:
            revisions.append("_".join(revision[:2]))
    if not revisions:
        raise RuntimeError("No Alembic revisions were found in migrations/versions")
    return sorted(revisions)[-1]


def _repair_legacy_schema(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    statements: list[str] = []
    if inspector.has_table("users"):
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "password_hash" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")
        if "password_reset_required" not in user_columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN password_reset_required BOOLEAN NOT NULL DEFAULT 0"
            )
        if "mfa_enabled" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN NOT NULL DEFAULT 0")
        if "mfa_pending_secret" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN mfa_pending_secret VARCHAR(96)")
        if "mfa_secret" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN mfa_secret VARCHAR(96)")
        if "mfa_confirmed_at" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN mfa_confirmed_at DATETIME")
        if "mfa_last_verified_at" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN mfa_last_verified_at DATETIME")
        if "permission_profile" not in user_columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN permission_profile VARCHAR(40) NOT NULL DEFAULT 'role_default'"
            )
        if "permission_overrides" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN permission_overrides JSON NOT NULL DEFAULT '{}'")
        if "external_identity_provider" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN external_identity_provider VARCHAR(80)")
        if "external_subject" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN external_subject VARCHAR(255)")
        if "external_last_login_at" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN external_last_login_at DATETIME")
        if "last_login_at" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN last_login_at DATETIME")

    if inspector.has_table("campaigns"):
        campaign_columns = {column["name"] for column in inspector.get_columns("campaigns")}
        if "template_name" not in campaign_columns:
            statements.append(
                "ALTER TABLE campaigns ADD COLUMN template_name VARCHAR(180) NOT NULL DEFAULT ''"
            )
        if "template_language" not in campaign_columns:
            statements.append(
                "ALTER TABLE campaigns ADD COLUMN template_language VARCHAR(20) NOT NULL DEFAULT 'en_US'"
            )
        if "template_variables" not in campaign_columns:
            statements.append(
                "ALTER TABLE campaigns ADD COLUMN template_variables JSON NOT NULL DEFAULT '[]'"
            )
        if "launched_at" not in campaign_columns:
            statements.append("ALTER TABLE campaigns ADD COLUMN launched_at DATETIME")
        if "completed_at" not in campaign_columns:
            statements.append("ALTER TABLE campaigns ADD COLUMN completed_at DATETIME")

    if inspector.has_table("knowledge_articles"):
        knowledge_columns = {
            column["name"] for column in inspector.get_columns("knowledge_articles")
        }
        if "submitted_for_review_at" not in knowledge_columns:
            statements.append(
                "ALTER TABLE knowledge_articles ADD COLUMN submitted_for_review_at DATETIME"
            )
        if "approved_at" not in knowledge_columns:
            statements.append("ALTER TABLE knowledge_articles ADD COLUMN approved_at DATETIME")
        if "approved_by" not in knowledge_columns:
            statements.append("ALTER TABLE knowledge_articles ADD COLUMN approved_by VARCHAR(180)")

    if not inspector.has_table("response_macros") and inspector.has_table("markets"):
        statements.append(
            """
            CREATE TABLE response_macros (
                id VARCHAR(64) NOT NULL PRIMARY KEY,
                market_id VARCHAR(64) NOT NULL,
                name VARCHAR(180) NOT NULL,
                body TEXT DEFAULT '',
                language VARCHAR(16) DEFAULT 'en',
                channels JSON NOT NULL DEFAULT '[]',
                tags JSON NOT NULL DEFAULT '[]',
                shortcut VARCHAR(80),
                active BOOLEAN NOT NULL DEFAULT 1,
                usage_count INTEGER NOT NULL DEFAULT 0,
                last_used_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(market_id) REFERENCES markets(id)
            )
            """
        )

    if inspector.has_table("tickets"):
        ticket_columns = {column["name"] for column in inspector.get_columns("tickets")}
        if "custom_fields" not in ticket_columns:
            statements.append("ALTER TABLE tickets ADD COLUMN custom_fields JSON NOT NULL DEFAULT '{}'")
        if "case_id" not in ticket_columns:
            statements.append("ALTER TABLE tickets ADD COLUMN case_id VARCHAR(64)")
        if "resolved_at" not in ticket_columns:
            statements.append("ALTER TABLE tickets ADD COLUMN resolved_at DATETIME")
        if "closed_at" not in ticket_columns:
            statements.append("ALTER TABLE tickets ADD COLUMN closed_at DATETIME")
        if "sla_resolution_met" not in ticket_columns:
            statements.append("ALTER TABLE tickets ADD COLUMN sla_resolution_met BOOLEAN")

    if inspector.has_table("support_groups"):
        support_group_columns = {
            column["name"] for column in inspector.get_columns("support_groups")
        }
        if "team_email" not in support_group_columns:
            statements.append(
                "ALTER TABLE support_groups ADD COLUMN team_email VARCHAR(255) NOT NULL DEFAULT ''"
            )

    if inspector.has_table("handoffs"):
        handoff_columns = {column["name"] for column in inspector.get_columns("handoffs")}
        if "linked_ticket_id" not in handoff_columns:
            statements.append("ALTER TABLE handoffs ADD COLUMN linked_ticket_id VARCHAR(64)")

    if inspector.has_table("workspace_settings"):
        workspace_columns = {
            column["name"] for column in inspector.get_columns("workspace_settings")
        }
        if "portal_logo_url" not in workspace_columns:
            statements.append(
                "ALTER TABLE workspace_settings ADD COLUMN portal_logo_url VARCHAR(500) NOT NULL DEFAULT ''"
            )
        if "portal_primary_color" not in workspace_columns:
            statements.append(
                "ALTER TABLE workspace_settings ADD COLUMN portal_primary_color VARCHAR(20) NOT NULL DEFAULT '#0b5eea'"
            )
        if "portal_support_name" not in workspace_columns:
            statements.append(
                "ALTER TABLE workspace_settings ADD COLUMN portal_support_name VARCHAR(160) NOT NULL DEFAULT ''"
            )
        if "portal_welcome_message" not in workspace_columns:
            statements.append(
                "ALTER TABLE workspace_settings ADD COLUMN portal_welcome_message TEXT NOT NULL DEFAULT ''"
            )

    if not inspector.has_table("ticket_fields") and inspector.has_table("markets"):
        statements.append(
            """
            CREATE TABLE ticket_fields (
                id VARCHAR(64) NOT NULL PRIMARY KEY,
                market_id VARCHAR(64) NOT NULL,
                key VARCHAR(64) NOT NULL,
                label VARCHAR(180) NOT NULL,
                field_type VARCHAR(32) DEFAULT 'text',
                required BOOLEAN NOT NULL DEFAULT 0,
                active BOOLEAN NOT NULL DEFAULT 1,
                system BOOLEAN NOT NULL DEFAULT 0,
                options JSON NOT NULL DEFAULT '[]',
                channels JSON NOT NULL DEFAULT '[]',
                placeholder VARCHAR(255) DEFAULT '',
                help_text TEXT DEFAULT '',
                position INTEGER NOT NULL DEFAULT 100,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(market_id) REFERENCES markets(id),
                CONSTRAINT uq_ticket_field_market_key UNIQUE (market_id, key)
            )
            """
        )

    if not inspector.has_table("support_groups") and inspector.has_table("markets"):
        statements.append(
            """
            CREATE TABLE support_groups (
                id VARCHAR(64) NOT NULL PRIMARY KEY,
                market_id VARCHAR(64) NOT NULL,
                name VARCHAR(120) NOT NULL,
                description TEXT DEFAULT '',
                team_email VARCHAR(255) NOT NULL DEFAULT '',
                active BOOLEAN NOT NULL DEFAULT 1,
                channels JSON NOT NULL DEFAULT '[]',
                skills JSON NOT NULL DEFAULT '[]',
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(market_id) REFERENCES markets(id),
                CONSTRAINT uq_support_group_market_name UNIQUE (market_id, name)
            )
            """
        )

    if not inspector.has_table("sla_policies") and inspector.has_table("markets"):
        statements.append(
            """
            CREATE TABLE sla_policies (
                id VARCHAR(64) NOT NULL PRIMARY KEY,
                market_id VARCHAR(64) NOT NULL,
                name VARCHAR(180) NOT NULL,
                active BOOLEAN NOT NULL DEFAULT 1,
                channels JSON NOT NULL DEFAULT '[]',
                priority VARCHAR(32) NOT NULL DEFAULT 'normal',
                first_response_minutes INTEGER NOT NULL DEFAULT 120,
                resolution_minutes INTEGER NOT NULL DEFAULT 1440,
                business_hours VARCHAR(120) NOT NULL DEFAULT 'Business hours',
                position INTEGER NOT NULL DEFAULT 100,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(market_id) REFERENCES markets(id),
                CONSTRAINT uq_sla_policy_market_name UNIQUE (market_id, name)
            )
            """
        )

    if not statements:
        return

    with Session(target_engine) as session:
        for statement in statements:
            session.execute(text(statement))
        fallback_password_hash = hash_password(token_urlsafe(48))
        session.execute(
            text(
                """
                UPDATE users
                SET password_hash = :password_hash,
                    password_reset_required = true
                WHERE password_hash IS NULL
                """
            ),
            {"password_hash": fallback_password_hash},
        )
        session.commit()


def _stamp_schema_head(target_engine: Engine) -> None:
    head_revision = _alembic_head_revision()
    inspector = inspect(target_engine)
    if inspector.has_table("alembic_version"):
        with Session(target_engine) as session:
            current_revision = session.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
            if current_revision is not None:
                if current_revision != head_revision:
                    session.execute(
                        text("UPDATE alembic_version SET version_num = :version_num"),
                        {"version_num": head_revision},
                    )
                    session.commit()
                return
    else:
        with Session(target_engine) as session:
            session.execute(
                text(
                    """
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(32) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    )
                    """
                )
            )
            session.commit()
    with Session(target_engine) as session:
        session.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"),
            {"version_num": head_revision},
        )
        session.commit()


def create_schema(engine: Engine | None = None) -> None:
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)
    _repair_legacy_schema(target_engine)
    _stamp_schema_head(target_engine)


def table_names(engine: Engine | None = None) -> list[str]:
    target_engine = engine or get_engine()
    return sorted(inspect(target_engine).get_table_names())


CONNECTOR_ACCOUNT_DEFAULTS: dict[str, dict] = {
    "email": {
        "status": "connected",
        "required_credentials": ["Mailbox OAuth or IMAP credentials", "SMTP or provider send API"],
        "capabilities": ["inbound sync", "outbound send", "thread mapping", "attachments"],
        "outbound_enabled": True,
        "webhook_verified": True,
        "secret_configured": True,
        "credential_ref": "local-dev:mailbox",
    },
    "whatsapp": {
        "status": "pending_credentials",
        "required_credentials": ["WhatsApp Business API token", "verified phone number", "message templates"],
        "capabilities": ["webhook intake", "template replies", "media", "delivery receipts"],
    },
    "facebook": {
        "status": "pending_credentials",
        "required_credentials": ["Meta app", "page access token", "webhook subscription"],
        "capabilities": ["Messenger DMs", "private replies", "delivery receipts"],
    },
    "instagram": {
        "status": "action_required",
        "required_credentials": ["Meta app", "Instagram business account", "webhook subscription"],
        "capabilities": ["Instagram DM", "comment-to-DM handoff", "media"],
        "last_error": "Business account review is required before live DM sync.",
        "failure_count": 1,
    },
    "sms": {
        "status": "pending_credentials",
        "required_credentials": ["SMS provider account", "sender ID", "delivery callback secret"],
        "capabilities": ["inbound text", "outbound text", "delivery receipts"],
    },
    "voice": {
        "status": "pending_credentials",
        "required_credentials": ["Voice provider account", "call webhook secret", "recording storage policy"],
        "capabilities": ["call logs", "callback requests", "voicemail summaries"],
    },
    "portal": {
        "status": "action_required",
        "required_credentials": [
            "Portal SSO or customer-auth provider",
            "Portal embed or widget secret",
            "Knowledge article access policy",
        ],
        "capabilities": ["authenticated updates", "case deflection", "attachment upload"],
        "outbound_enabled": True,
        "last_error": "Portal identity integration is not configured for this market yet.",
        "failure_count": 1,
    },
    "api": {
        "status": "action_required",
        "required_credentials": [
            "Partner webhook signing secret",
            "Allowlisted callback endpoint",
            "Partner event schema mapping",
        ],
        "capabilities": ["webhook intake", "idempotency", "replay protection", "partner callbacks"],
        "outbound_enabled": True,
        "last_error": "Partner callback credentials are required before live API exchange is enabled.",
        "failure_count": 1,
    },
}


def _connector_identifier(market: MarketRecord, provider: str) -> str:
    if provider == "email":
        return market.support_email
    if provider == "whatsapp":
        return market.whatsapp_number or ""
    if provider == "facebook":
        return market.facebook_page or ""
    if provider == "instagram":
        return market.instagram_handle or ""
    if provider == "sms":
        return f"{market.code} sender ID pending"
    if provider == "voice":
        return f"{market.code} voice line pending"
    if provider == "portal":
        return f"{market.code} customer portal pending"
    if provider == "api":
        return f"{market.code} partner API pending"
    return ""


def seed_connector_accounts(session: Session) -> None:
    markets = session.scalars(select(MarketRecord)).all()
    for market in markets:
        for provider, defaults in CONNECTOR_ACCOUNT_DEFAULTS.items():
            existing = session.scalar(
                select(ConnectorAccountRecord).where(
                    ConnectorAccountRecord.market_id == market.id,
                    ConnectorAccountRecord.provider == provider,
                )
            )
            if existing is not None:
                continue
            account = ConnectorAccountRecord(
                id=f"connector-{market.code.lower()}-{provider}",
                market_id=market.id,
                provider=provider,
                display_name=f"{market.name} {provider.replace('_', ' ').title()}",
                account_identifier=_connector_identifier(market, provider),
                status=defaults["status"],
                intake_enabled=defaults.get("status") not in {"disabled", "error"},
                outbound_enabled=defaults.get("outbound_enabled", False),
                webhook_url=f"/api/v1/webhooks/{provider}/{market.code.lower()}",
                webhook_verified=defaults.get("webhook_verified", False),
                credential_ref=defaults.get("credential_ref"),
                secret_configured=defaults.get("secret_configured", False),
                last_error=defaults.get("last_error"),
                failure_count=defaults.get("failure_count", 0),
                required_credentials=defaults["required_credentials"],
                capabilities=defaults["capabilities"],
            )
            session.add(account)
    session.commit()


def seed_response_macros(session: Session, source: InMemoryStore = store) -> None:
    for macro in source.response_macros.values():
        existing = session.get(ResponseMacroRecord, macro.id)
        if existing is not None:
            continue
        session.add(ResponseMacroRecord(**_payload(macro)))
    session.commit()


def seed_ticket_fields(session: Session, source: InMemoryStore = store) -> None:
    for field in source.ticket_fields.values():
        existing = session.get(TicketFieldRecord, field.id) or session.scalar(
            select(TicketFieldRecord).where(
                TicketFieldRecord.market_id == field.market_id,
                TicketFieldRecord.key == field.key,
            )
        )
        if existing is not None:
            continue
        session.add(TicketFieldRecord(**_payload(field)))
    session.commit()


def seed_support_groups(session: Session, source: InMemoryStore = store) -> None:
    for group in source.support_groups.values():
        existing = session.get(SupportGroupRecord, group.id) or session.scalar(
            select(SupportGroupRecord).where(
                SupportGroupRecord.market_id == group.market_id,
                SupportGroupRecord.name == group.name,
            )
        )
        if existing is not None:
            if not existing.team_email and group.team_email:
                existing.team_email = str(group.team_email)
            continue
        payload = _payload(group)
        payload.pop("member_count", None)
        payload.pop("open_ticket_count", None)
        payload.pop("sla_risk_count", None)
        session.add(SupportGroupRecord(**payload))
    session.commit()


def seed_sla_policies(session: Session, source: InMemoryStore = store) -> None:
    for policy in source.sla_policies.values():
        existing = session.get(SlaPolicyRecord, policy.id) or session.scalar(
            select(SlaPolicyRecord).where(
                SlaPolicyRecord.market_id == policy.market_id,
                SlaPolicyRecord.name == policy.name,
            )
        )
        if existing is not None:
            continue
        session.add(SlaPolicyRecord(**_payload(policy)))
    session.commit()


def seed_business_hours(session: Session, source: InMemoryStore = store) -> None:
    for calendar in source.business_hours.values():
        existing = session.get(BusinessHoursRecord, calendar.id) or session.scalar(
            select(BusinessHoursRecord).where(
                BusinessHoursRecord.market_id == calendar.market_id,
                BusinessHoursRecord.name == calendar.name,
            )
        )
        if existing is not None:
            continue
        session.add(BusinessHoursRecord(**_payload(calendar)))
    session.commit()


def seed_ticket_templates(session: Session, source: InMemoryStore = store) -> None:
    for template in source.ticket_templates.values():
        existing = session.get(TicketTemplateRecord, template.id) or session.scalar(
            select(TicketTemplateRecord).where(
                TicketTemplateRecord.market_id == template.market_id,
                TicketTemplateRecord.name == template.name,
            )
        )
        if existing is not None:
            continue
        session.add(TicketTemplateRecord(**_payload(template)))
    session.commit()


def seed_tags(session: Session, source: InMemoryStore = store) -> None:
    for tag in source.tags.values():
        existing = session.get(TagRecord, tag.id) or session.scalar(
            select(TagRecord).where(
                TagRecord.market_id == tag.market_id,
                TagRecord.name == tag.name,
            )
        )
        if existing is not None:
            continue
        session.add(TagRecord(**_payload(tag)))
    session.commit()


def seed_csat_surveys(session: Session, source: InMemoryStore = store) -> None:
    for survey in source.csat_surveys.values():
        existing = session.get(CsatSurveyRecord, survey.id) or session.scalar(
            select(CsatSurveyRecord).where(
                CsatSurveyRecord.market_id == survey.market_id,
                CsatSurveyRecord.name == survey.name,
            )
        )
        if existing is not None:
            continue
        session.add(CsatSurveyRecord(**_payload(survey)))
    session.commit()


def seed_email_notifications(session: Session, source: InMemoryStore = store) -> None:
    for notification in source.email_notifications.values():
        existing = session.get(EmailNotificationRecord, notification.id) or session.scalar(
            select(EmailNotificationRecord).where(
                EmailNotificationRecord.market_id == notification.market_id,
                EmailNotificationRecord.name == notification.name,
            )
        )
        if existing is not None:
            continue
        session.add(EmailNotificationRecord(**_payload(notification)))
    session.commit()


def seed_scenario_automations(session: Session, source: InMemoryStore = store) -> None:
    for scenario in source.scenario_automations.values():
        existing = session.get(ScenarioAutomationRecord, scenario.id) or session.scalar(
            select(ScenarioAutomationRecord).where(
                ScenarioAutomationRecord.market_id == scenario.market_id,
                ScenarioAutomationRecord.name == scenario.name,
            )
        )
        if existing is not None:
            continue
        session.add(ScenarioAutomationRecord(**_payload(scenario)))
    session.commit()


def seed_custom_field_definitions(session: Session, source: InMemoryStore = store) -> None:
    for field in source.custom_field_definitions.values():
        existing = session.get(CustomFieldDefinitionRecord, field.id) or session.scalar(
            select(CustomFieldDefinitionRecord).where(
                CustomFieldDefinitionRecord.market_id == field.market_id,
                CustomFieldDefinitionRecord.entity == field.entity,
                CustomFieldDefinitionRecord.key == field.key,
            )
        )
        if existing is not None:
            continue
        session.add(CustomFieldDefinitionRecord(**_payload(field)))
    session.commit()


def seed_custom_objects(session: Session, source: InMemoryStore = store) -> None:
    for custom_object in source.custom_objects.values():
        existing = session.get(CustomObjectRecord, custom_object.id) or session.scalar(
            select(CustomObjectRecord).where(
                CustomObjectRecord.market_id == custom_object.market_id,
                CustomObjectRecord.key == custom_object.key,
            )
        )
        if existing is not None:
            continue
        session.add(CustomObjectRecord(**_payload(custom_object)))
    session.commit()


def seed_products(session: Session, source: InMemoryStore = store) -> None:
    for product in source.products.values():
        existing = session.get(ProductRecord, product.id) or session.scalar(
            select(ProductRecord).where(
                ProductRecord.market_id == product.market_id,
                ProductRecord.name == product.name,
            )
        )
        if existing is not None:
            continue
        session.add(ProductRecord(**_payload(product)))
    session.commit()


def seed_saved_reports(session: Session, source: InMemoryStore = store) -> None:
    for report in source.saved_reports.values():
        existing = session.get(SavedReportRecord, report.id) or session.scalar(
            select(SavedReportRecord).where(
                SavedReportRecord.market_id == report.market_id,
                SavedReportRecord.name == report.name,
            )
        )
        if existing is not None:
            continue
        session.add(SavedReportRecord(**_payload(report)))
    session.commit()


def seed_service_appointments(session: Session, source: InMemoryStore = store) -> None:
    for appointment in source.service_appointments.values():
        if session.get(ServiceAppointmentRecord, appointment.id) is not None:
            continue
        data = appointment.model_dump(exclude={"created_at", "updated_at"})
        session.add(ServiceAppointmentRecord(**data))
    session.commit()


def seed_discussion_topics(session: Session, source: InMemoryStore = store) -> None:
    for topic in source.discussion_topics.values():
        if session.get(DiscussionTopicRecord, topic.id) is not None:
            continue
        session.add(DiscussionTopicRecord(**_payload(topic)))
    for comment in source.discussion_comments.values():
        if session.get(DiscussionCommentRecord, comment.id) is not None:
            continue
        session.add(DiscussionCommentRecord(**_payload(comment)))
    session.commit()


def ensure_qa_admin(session: Session) -> None:
    if not settings.qa_admin_enabled:
        return
    email = (settings.qa_admin_email or "").strip().lower()
    password = settings.qa_admin_password or ""
    requested_market_ids = [
        value.strip() for value in settings.qa_admin_market_ids.split(",") if value.strip()
    ]
    active_market_ids = set(
        session.scalars(
            select(MarketRecord.id).where(
                MarketRecord.id.in_(requested_market_ids),
                MarketRecord.active.is_(True),
            )
        )
    )
    market_ids = [market_id for market_id in requested_market_ids if market_id in active_market_ids]
    if not market_ids:
        raise RuntimeError("QA administrator has no active assigned market.")
    record = session.scalar(select(UserRecord).where(UserRecord.email == email))
    if record is None:
        record = UserRecord(
            id="user-vercel-qa-admin",
            name="Omni QA Administrator",
            email=email,
            password_hash=hash_password(password),
            password_reset_required=False,
            role="admin",
            default_market_id=market_ids[0],
            market_ids=market_ids,
            active=True,
            permission_profile="role_default",
            permission_overrides={},
        )
        session.add(record)
    else:
        record.name = "Omni QA Administrator"
        record.role = "admin"
        record.default_market_id = market_ids[0]
        record.market_ids = market_ids
        record.active = True
        record.password_reset_required = False
        if not verify_password(password, record.password_hash):
            record.password_hash = hash_password(password)
            record.mfa_enabled = False
            record.mfa_pending_secret = None
            record.mfa_secret = None
            record.mfa_confirmed_at = None
            record.mfa_last_verified_at = None
    session.flush()


def seed_reference_data(session: Session, source: InMemoryStore = store) -> None:
    if settings.production_like:
        raise RuntimeError(
            "Fixture seeding is disabled in staging/production. Use migrations and onboarding."
        )
    if session.scalar(select(MarketRecord.id).limit(1)):
        seed_connector_accounts(session)
        seed_response_macros(session, source)
        seed_ticket_fields(session, source)
        seed_support_groups(session, source)
        seed_sla_policies(session, source)
        seed_business_hours(session, source)
        seed_ticket_templates(session, source)
        seed_tags(session, source)
        seed_csat_surveys(session, source)
        seed_email_notifications(session, source)
        seed_scenario_automations(session, source)
        seed_custom_field_definitions(session, source)
        seed_custom_objects(session, source)
        seed_products(session, source)
        seed_saved_reports(session, source)
        seed_service_appointments(session, source)
        seed_discussion_topics(session, source)
        ensure_qa_admin(session)
        session.commit()
        return

    session.add_all(
        [
            MarketRecord(**_payload(market))
            for market in source.markets.values()
        ]
    )
    session.flush()
    user_records = []
    for user in source.users.values():
        payload = _payload(user)
        payload.pop("effective_permissions", None)
        payload["password_hash"] = hash_password("omni-demo")
        payload["password_reset_required"] = False
        user_records.append(UserRecord(**payload))
    session.add_all(user_records)
    session.add_all(
        [
            WorkspaceSettingsRecord(**_payload(settings))
            for settings in source.settings_by_market.values()
        ]
    )
    session.add_all(
        [
            ChannelRecord(
                **{
                    key: value
                    for key, value in _payload(channel).items()
                    # Wiring/readiness fields are computed at read time, never stored.
                    if key not in {"intake_live", "intake_note", "outbound_live", "outbound_note"}
                }
            )
            for channel in source.channels.values()
        ]
    )
    session.add_all(
        [
            AgentRecord(
                id=agent.id,
                market_ids=agent.market_ids,
                name=agent.name,
                email=str(agent.email),
                role=agent.team,
                status=agent.status.value,
                occupancy=agent.occupancy,
                capacity=agent.capacity,
                skills=[skill.value for skill in agent.skills],
                languages=agent.languages,
            )
            for agent in source.agents.values()
        ]
    )
    for group in source.support_groups.values():
        payload = _payload(group)
        payload.pop("member_count", None)
        payload.pop("open_ticket_count", None)
        payload.pop("sla_risk_count", None)
        session.add(SupportGroupRecord(**payload))
    session.add_all(
        [
            SlaPolicyRecord(**_payload(policy))
            for policy in source.sla_policies.values()
        ]
    )
    session.add_all(
        [
            BusinessHoursRecord(**_payload(calendar))
            for calendar in source.business_hours.values()
        ]
    )
    session.add_all(
        [
            TicketTemplateRecord(**_payload(template))
            for template in source.ticket_templates.values()
        ]
    )
    session.add_all(
        [TagRecord(**_payload(tag)) for tag in source.tags.values()]
    )
    session.add_all(
        [CsatSurveyRecord(**_payload(survey)) for survey in source.csat_surveys.values()]
    )
    session.add_all(
        [
            EmailNotificationRecord(**_payload(notification))
            for notification in source.email_notifications.values()
        ]
    )
    session.add_all(
        [
            ScenarioAutomationRecord(**_payload(scenario))
            for scenario in source.scenario_automations.values()
        ]
    )
    session.add_all(
        [
            CustomFieldDefinitionRecord(**_payload(field))
            for field in source.custom_field_definitions.values()
        ]
    )
    session.add_all(
        [
            CustomObjectRecord(**_payload(custom_object))
            for custom_object in source.custom_objects.values()
        ]
    )
    session.add_all(
        [ProductRecord(**_payload(product)) for product in source.products.values()]
    )
    session.add_all(
        [SavedReportRecord(**_payload(report)) for report in source.saved_reports.values()]
    )
    session.add_all(
        [
            ServiceAppointmentRecord(
                **appointment.model_dump(exclude={"created_at", "updated_at"})
            )
            for appointment in source.service_appointments.values()
        ]
    )
    session.add_all(
        [
            DiscussionTopicRecord(**_payload(topic))
            for topic in source.discussion_topics.values()
        ]
    )
    session.add_all(
        [
            CompanyRecord(**_payload(company))
            for company in source.companies.values()
        ]
    )
    session.flush()
    session.add_all(
        [
            DiscussionCommentRecord(**_payload(comment))
            for comment in source.discussion_comments.values()
        ]
    )
    session.add_all(
        [
            CustomerRecord(**_payload(customer))
            for customer in source.customers.values()
        ]
    )
    session.add_all(
        [
            KnowledgeArticleRecord(**_payload(article))
            for article in source.knowledge.values()
        ]
    )
    session.add_all(
        [
            ResponseMacroRecord(**_payload(macro))
            for macro in source.response_macros.values()
        ]
    )
    session.add_all(
        [
            TicketFieldRecord(**_payload(field))
            for field in source.ticket_fields.values()
        ]
    )
    session.add_all(
        [
            AutomationRuleRecord(**_payload(rule))
            for rule in source.rules.values()
        ]
    )
    session.flush()
    session.add_all(
        [
            TicketRecord(**_payload(ticket))
            for ticket in source.tickets.values()
        ]
    )
    session.flush()
    session.add_all(
        [
            TimelineEventRecord(
                **{key: value for key, value in payload.items() if key != "metadata"},
                market_id=source.tickets[event.ticket_id].market_id,
                event_metadata=payload["metadata"],
            )
            for events in source.timeline.values()
            for event in events
            for payload in [_payload(event)]
        ]
    )
    session.add_all(
        [
            HandoffRecord(**_payload(handoff))
            for handoff in source.handoffs.values()
        ]
    )
    session.add_all(
        [
            ConnectorEventRecord(**_payload(event))
            for event in source.connector_events.values()
        ]
    )
    session.flush()
    seed_connector_accounts(session)
    session.add_all(
        [
            AiDecisionRecord(
                id=decision.id,
                market_id=source.tickets[decision.ticket_id].market_id,
                ticket_id=decision.ticket_id,
                decision_type=decision.decision_type,
                confidence=int(round(decision.confidence * 100)),
                summary=decision.summary,
                model_version=decision.model_version,
                input_reference=decision.input_reference,
                override_allowed=decision.override_allowed,
                created_at=decision.created_at,
            )
            for decision in source.ai_decisions
        ]
    )
    session.add_all(
        [
            AuditEventRecord(**_payload(event))
            for event in source.audit
        ]
    )
    session.flush()
    seed_demo_dashboard_data(session)
    ensure_qa_admin(session)
    session.commit()


def seed_demo_dashboard_data(session: Session) -> None:
    """Idempotently group one customer's multi-channel tickets into a demo Case so the
    Phase-2 case feature is visible in a freshly-seeded workspace out of the box.

    Deliberately seeds only this *structural* example — NOT fabricated CSAT scores or
    resolution stats. Performance metrics (CSAT, resolution-within-SLA) stay honest and
    populate from real activity rather than being faked by the seed."""
    for market in session.scalars(select(MarketRecord)).all():
        if session.scalar(
            select(CaseRecord.id).where(CaseRecord.market_id == market.id).limit(1)
        ):
            continue
        tickets = list(
            session.scalars(
                select(TicketRecord)
                .where(TicketRecord.market_id == market.id)
                .order_by(TicketRecord.public_id)
            ).all()
        )
        by_customer: dict[str, list[TicketRecord]] = {}
        for ticket in tickets:
            by_customer.setdefault(ticket.customer_id, []).append(ticket)
        for customer_id, customer_tickets in by_customer.items():
            channels = {ticket.channel for ticket in customer_tickets}
            if len(customer_tickets) >= 2 and len(channels) >= 2:
                case_id = f"seed-case-{market.id}"
                session.add(
                    CaseRecord(
                        id=case_id,
                        market_id=market.id,
                        public_id=f"CASE-{market.code.upper()}-1",
                        customer_id=customer_id,
                        title=customer_tickets[0].subject,
                        status="open",
                        priority=customer_tickets[0].priority,
                        summary="Same customer reached out across multiple channels.",
                        opened_by="seed",
                    )
                )
                for ticket in customer_tickets:
                    ticket.case_id = case_id
                break


def initialize_database(engine: Engine | None = None) -> None:
    if settings.production_like:
        raise RuntimeError(
            "Runtime database initialization is disabled in staging/production."
        )
    target_engine = engine or get_engine()
    create_schema(target_engine)
    with Session(target_engine) as session:
        seed_reference_data(session)
        hydrate_store_state(session, store)


def reset_database(engine: Engine | None = None, source: InMemoryStore = store) -> None:
    target_engine = engine or get_engine()
    Base.metadata.drop_all(bind=target_engine)
    create_schema(target_engine)
    with Session(target_engine) as session:
        seed_reference_data(session, source)
        hydrate_store_state(session, source)
