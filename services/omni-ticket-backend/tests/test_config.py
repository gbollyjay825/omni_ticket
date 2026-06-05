import pytest

from app.core.config import Settings


def test_local_settings_allow_sqlite_and_seed_initialization() -> None:
    settings = Settings(
        environment="local",
        database_url="sqlite:///./data/test.db",
        initialize_database=True,
        allowed_origins=["http://127.0.0.1:5173"],
    )

    assert settings.deployment_errors("web") == []


def test_production_settings_require_postgres_explicit_migrations_and_frontend_origin() -> None:
    settings = Settings(
        environment="production",
        database_url="sqlite:///./data/test.db",
        initialize_database=True,
        allowed_origins=["*"],
    )

    errors = settings.deployment_errors("web")

    assert any("PostgreSQL" in error for error in errors)
    assert any("OMNI_INITIALIZE_DATABASE" in error for error in errors)
    assert any("OMNI_SESSION_SECRET" in error for error in errors)
    assert any("cannot contain '*'" in error for error in errors)
    assert any("OMNI_OUTBOUND_LOCAL_ADAPTER_ENABLED" in error for error in errors)


def test_validate_for_process_raises_for_invalid_production_config() -> None:
    settings = Settings(environment="production", database_url="sqlite:///./data/test.db")

    with pytest.raises(RuntimeError):
        settings.validate_for_process("worker")


def test_rate_limit_settings_must_be_positive() -> None:
    settings = Settings(
        login_rate_limit_attempts=0,
        connector_inbound_rate_limit_window_seconds=0,
        webhook_rate_limit_attempts=0,
        portal_rate_limit_window_seconds=0,
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_LOGIN_RATE_LIMIT_ATTEMPTS" in error for error in errors)
    assert any("OMNI_CONNECTOR_INBOUND_RATE_LIMIT_WINDOW_SECONDS" in error for error in errors)
    assert any("OMNI_WEBHOOK_RATE_LIMIT_ATTEMPTS" in error for error in errors)
    assert any("OMNI_PORTAL_RATE_LIMIT_WINDOW_SECONDS" in error for error in errors)


def test_audit_retention_settings_are_validated() -> None:
    settings = Settings(audit_retention_days=7, audit_export_max_rows=0)

    errors = settings.deployment_errors("worker")

    assert any("OMNI_AUDIT_RETENTION_DAYS" in error for error in errors)
    assert any("OMNI_AUDIT_EXPORT_MAX_ROWS" in error for error in errors)


def test_ai_provider_settings_are_validated() -> None:
    settings = Settings(
        ai_provider="anthropic",
        anthropic_api_key_file=None,
        anthropic_timeout_seconds=0,
        anthropic_max_tokens=0,
        anthropic_api_base_url="",
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_ANTHROPIC_API_KEY" in error for error in errors)
    assert any("OMNI_ANTHROPIC_TIMEOUT_SECONDS" in error for error in errors)
    assert any("OMNI_ANTHROPIC_MAX_TOKENS" in error for error in errors)
    assert any("OMNI_ANTHROPIC_API_BASE_URL" in error for error in errors)

    invalid_provider = Settings(ai_provider="open-ended")

    assert any("OMNI_AI_PROVIDER" in error for error in invalid_provider.deployment_errors("web"))


def test_attachment_retention_settings_are_validated() -> None:
    settings = Settings(
        attachment_retention_days=7,
        attachment_deleted_retention_days=0,
        attachment_retention_prune_limit=0,
    )

    errors = settings.deployment_errors("worker")

    assert any("OMNI_ATTACHMENT_RETENTION_DAYS" in error for error in errors)
    assert any("OMNI_ATTACHMENT_DELETED_RETENTION_DAYS" in error for error in errors)
    assert any("OMNI_ATTACHMENT_RETENTION_PRUNE_LIMIT" in error for error in errors)


def test_attachment_storage_and_scanner_settings_are_validated() -> None:
    settings = Settings(
        attachment_storage_backend="s3",
        attachment_s3_access_key_id="access-key",
        attachment_scanner_adapter="http",
        attachment_scanner_http_timeout_seconds=0,
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_ATTACHMENT_S3_BUCKET" in error for error in errors)
    assert any("OMNI_ATTACHMENT_S3_REGION or OMNI_ATTACHMENT_S3_ENDPOINT_URL" in error for error in errors)
    assert any("OMNI_ATTACHMENT_S3_SECRET_ACCESS_KEY" in error for error in errors)
    assert any("OMNI_ATTACHMENT_SCANNER_HTTP_ENDPOINT" in error for error in errors)
    assert any("OMNI_ATTACHMENT_SCANNER_HTTP_TIMEOUT_SECONDS" in error for error in errors)


def test_attachment_storage_and_scanner_modes_are_validated() -> None:
    settings = Settings(
        attachment_storage_backend="ftp",
        attachment_scanner_adapter="clamav",
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_ATTACHMENT_STORAGE_BACKEND" in error for error in errors)
    assert any("OMNI_ATTACHMENT_SCANNER_ADAPTER" in error for error in errors)


def test_oidc_identity_settings_are_validated() -> None:
    settings = Settings(
        oidc_enabled=True,
        oidc_client_id="omni-client",
        oidc_http_timeout_seconds=0,
        oidc_state_ttl_minutes=0,
        oidc_auto_provision_enabled=True,
        oidc_default_role="owner",
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_OIDC_AUTHORIZATION_URL" in error for error in errors)
    assert any("OMNI_OIDC_TOKEN_URL" in error for error in errors)
    assert any("OMNI_OIDC_USERINFO_URL" in error for error in errors)
    assert any("OMNI_OIDC_CLIENT_SECRET" in error for error in errors)
    assert any("OMNI_OIDC_REDIRECT_URL" in error for error in errors)
    assert any("OMNI_OIDC_HTTP_TIMEOUT_SECONDS" in error for error in errors)
    assert any("OMNI_OIDC_STATE_TTL_MINUTES" in error for error in errors)
    assert any("OMNI_OIDC_DEFAULT_ROLE" in error for error in errors)
    assert any("OMNI_OIDC_DEFAULT_MARKET_ID" in error for error in errors)

    partial_settings = Settings(oidc_authorization_url="https://id.example.com/authorize")

    assert any("OMNI_OIDC_ENABLED" in error for error in partial_settings.deployment_errors("web"))


def test_production_oidc_urls_must_use_https() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://omni:secret@db/omni",
        initialize_database=False,
        session_secret="not-local",
        outbound_local_adapter_enabled=False,
        allowed_origins=["https://omni.wakanow.com"],
        oidc_enabled=True,
        oidc_authorization_url="http://id.example.com/authorize",
        oidc_token_url="http://id.example.com/token",
        oidc_userinfo_url="http://id.example.com/userinfo",
        oidc_client_id="omni-client",
        oidc_client_secret="secret",
        oidc_redirect_url="http://omni.wakanow.com/auth/callback",
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_OIDC_AUTHORIZATION_URL" in error for error in errors)
    assert any("OMNI_OIDC_TOKEN_URL" in error for error in errors)
    assert any("OMNI_OIDC_USERINFO_URL" in error for error in errors)
    assert any("OMNI_OIDC_REDIRECT_URL" in error for error in errors)


def test_smtp_settings_are_validated() -> None:
    settings = Settings(
        email_smtp_host="smtp.example.com",
        email_smtp_port=0,
        email_smtp_use_starttls=True,
        email_smtp_use_ssl=True,
        email_smtp_password="secret",
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_EMAIL_SMTP_PORT" in error for error in errors)
    assert any("OMNI_EMAIL_SMTP_USE_SSL" in error for error in errors)
    assert any("OMNI_EMAIL_SMTP_PASSWORD" in error for error in errors)


def test_imap_settings_are_validated_when_polling_is_enabled() -> None:
    settings = Settings(
        email_imap_poll_enabled=True,
        email_imap_port=0,
        email_imap_timeout_seconds=0,
        email_imap_fetch_limit=0,
        email_imap_password="secret",
    )

    errors = settings.deployment_errors("worker")

    assert any("OMNI_EMAIL_IMAP_HOST" in error for error in errors)
    assert any("OMNI_EMAIL_IMAP_USERNAME" in error for error in errors)
    assert any("OMNI_EMAIL_IMAP_PASSWORD requires" in error for error in errors)
    assert any("OMNI_EMAIL_IMAP_PORT" in error for error in errors)
    assert any("OMNI_EMAIL_IMAP_TIMEOUT_SECONDS" in error for error in errors)
    assert any("OMNI_EMAIL_IMAP_FETCH_LIMIT" in error for error in errors)


def test_sms_http_settings_are_validated() -> None:
    settings = Settings(
        sms_http_endpoint="https://sms.example.com/messages",
        sms_http_timeout_seconds=0,
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_SMS_HTTP_TIMEOUT_SECONDS" in error for error in errors)
    assert any("OMNI_SMS_HTTP_FROM" in error for error in errors)
    assert any("OMNI_SMS_HTTP_AUTH_TOKEN" in error for error in errors)

    partial_settings = Settings(sms_http_auth_token="secret")

    assert any("OMNI_SMS_HTTP_ENDPOINT" in error for error in partial_settings.deployment_errors("web"))


def test_whatsapp_cloud_api_settings_are_validated() -> None:
    settings = Settings(
        whatsapp_phone_number_id="1234567890",
        whatsapp_timeout_seconds=0,
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_WHATSAPP_TIMEOUT_SECONDS" in error for error in errors)
    assert any("OMNI_WHATSAPP_ACCESS_TOKEN" in error for error in errors)

    partial_settings = Settings(whatsapp_access_token="secret")

    assert any(
        "OMNI_WHATSAPP_PHONE_NUMBER_ID" in error
        for error in partial_settings.deployment_errors("web")
    )


def test_facebook_messenger_settings_are_validated() -> None:
    settings = Settings(
        facebook_page_id="page-123",
        facebook_timeout_seconds=0,
        facebook_messaging_type="INVALID",
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_FACEBOOK_TIMEOUT_SECONDS" in error for error in errors)
    assert any("OMNI_FACEBOOK_PAGE_ACCESS_TOKEN" in error for error in errors)
    assert any("OMNI_FACEBOOK_MESSAGING_TYPE" in error for error in errors)

    partial_settings = Settings(facebook_page_access_token="secret")

    assert any(
        "OMNI_FACEBOOK_PAGE_ID" in error
        for error in partial_settings.deployment_errors("web")
    )


def test_instagram_dm_settings_are_validated() -> None:
    settings = Settings(
        instagram_business_account_id="ig-business-123",
        instagram_timeout_seconds=0,
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_INSTAGRAM_TIMEOUT_SECONDS" in error for error in errors)
    assert any("OMNI_INSTAGRAM_ACCESS_TOKEN" in error for error in errors)

    partial_settings = Settings(instagram_access_token="secret")

    assert any(
        "OMNI_INSTAGRAM_BUSINESS_ACCOUNT_ID" in error
        for error in partial_settings.deployment_errors("web")
    )


def test_voice_http_settings_are_validated() -> None:
    settings = Settings(
        voice_http_endpoint="https://voice.example.test/calls",
        voice_http_timeout_seconds=0,
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_VOICE_HTTP_TIMEOUT_SECONDS" in error for error in errors)
    assert any("OMNI_VOICE_HTTP_FROM" in error for error in errors)
    assert any("OMNI_VOICE_HTTP_AUTH_TOKEN" in error for error in errors)

    partial_settings = Settings(voice_http_auth_token="secret")

    assert any(
        "OMNI_VOICE_HTTP_ENDPOINT" in error
        for error in partial_settings.deployment_errors("web")
    )
