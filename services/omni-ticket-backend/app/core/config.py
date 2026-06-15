from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Omni Ticket Backend"
    environment: str = "local"
    api_prefix: str = "/api/v1"
    public_app_url: str = "https://omni.wakanow.com"
    database_url: str = "sqlite:///./data/omni-ticket.db"
    database_echo: bool = False
    initialize_database: bool = True
    worker_interval_seconds: int = 60
    worker_outbound_limit: int = 50
    # Auto-close resolved tickets after this many hours with no further activity.
    # Set to 0 to disable auto-close.
    auto_close_resolved_after_hours: int = 72
    session_secret: str = "omni-ticket-local-dev-secret"
    session_ttl_minutes: int = 8 * 60
    webhook_signature_tolerance_seconds: int = 5 * 60
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_seconds: int = 60
    connector_inbound_rate_limit_attempts: int = 120
    connector_inbound_rate_limit_window_seconds: int = 60
    webhook_rate_limit_attempts: int = 120
    webhook_rate_limit_window_seconds: int = 60
    portal_rate_limit_attempts: int = 30
    portal_rate_limit_window_seconds: int = 60
    attachment_storage_dir: str = "/tmp/omni-ticket-attachments"
    attachment_storage_backend: str = "local"
    attachment_s3_bucket: str | None = None
    attachment_s3_prefix: str = "omni-ticket/attachments"
    attachment_s3_region: str | None = None
    attachment_s3_endpoint_url: str | None = None
    attachment_s3_access_key_id: str | None = None
    attachment_s3_secret_access_key: str | None = None
    attachment_s3_server_side_encryption: str | None = "AES256"
    attachment_scanner_adapter: str = "local"
    attachment_scanner_http_endpoint: str | None = None
    attachment_scanner_http_auth_token: str | None = None
    attachment_scanner_http_auth_header: str = "Authorization"
    attachment_scanner_http_auth_scheme: str = "Bearer"
    attachment_scanner_http_timeout_seconds: int = 10
    attachment_max_bytes: int = 25 * 1024 * 1024
    attachment_download_ttl_minutes: int = 10
    handoff_attachment_download_ttl_minutes: int = 7 * 24 * 60
    attachment_retention_days: int = 365
    attachment_deleted_retention_days: int = 30
    attachment_retention_prune_limit: int = 250
    audit_retention_days: int = 365
    audit_export_max_rows: int = 5000
    outbound_local_adapter_enabled: bool = True
    ai_provider: str = "auto"
    anthropic_api_key: str | None = None
    anthropic_api_key_file: str | None = "AI_Key"
    anthropic_api_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_version: str = "2023-06-01"
    anthropic_timeout_seconds: int = 12
    anthropic_max_tokens: int = 600
    email_smtp_host: str | None = None
    email_smtp_port: int = 587
    email_smtp_username: str | None = None
    email_smtp_password: str | None = None
    email_smtp_from_email: str | None = None
    email_smtp_use_starttls: bool = True
    email_smtp_use_ssl: bool = False
    email_smtp_timeout_seconds: int = 15
    email_imap_poll_enabled: bool = False
    email_imap_host: str | None = None
    email_imap_port: int = 993
    email_imap_username: str | None = None
    email_imap_password: str | None = None
    email_imap_mailbox: str = "INBOX"
    email_imap_use_ssl: bool = True
    email_imap_timeout_seconds: int = 15
    email_imap_fetch_limit: int = 25
    email_imap_mark_seen: bool = True
    sms_http_endpoint: str | None = None
    sms_http_auth_token: str | None = None
    sms_http_from: str | None = None
    sms_http_auth_header: str = "Authorization"
    sms_http_auth_scheme: str = "Bearer"
    sms_http_delivery_callback_url: str | None = None
    sms_http_timeout_seconds: int = 10
    voice_http_endpoint: str | None = None
    voice_http_auth_token: str | None = None
    voice_http_from: str | None = None
    voice_http_auth_header: str = "Authorization"
    voice_http_auth_scheme: str = "Bearer"
    voice_http_status_callback_url: str | None = None
    voice_http_timeout_seconds: int = 10
    whatsapp_cloud_api_base_url: str = "https://graph.facebook.com/v25.0"
    whatsapp_phone_number_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_preview_urls: bool = False
    whatsapp_timeout_seconds: int = 10
    facebook_graph_api_base_url: str = "https://graph.facebook.com/v25.0"
    facebook_page_id: str | None = None
    facebook_page_access_token: str | None = None
    facebook_messaging_type: str = "RESPONSE"
    facebook_timeout_seconds: int = 10
    instagram_graph_api_base_url: str = "https://graph.instagram.com/v25.0"
    instagram_business_account_id: str | None = None
    instagram_access_token: str | None = None
    instagram_timeout_seconds: int = 10
    alert_webhook_url: str | None = None
    alert_webhook_secret: str | None = None
    alert_webhook_timeout_seconds: int = 8
    alert_delivery_max_attempts: int = 3
    alert_delivery_retry_minutes: int = 15
    alert_delivery_min_severity: str = "warning"
    oidc_enabled: bool = False
    oidc_provider_name: str = "Enterprise SSO"
    oidc_issuer_url: str | None = None
    oidc_authorization_url: str | None = None
    oidc_token_url: str | None = None
    oidc_userinfo_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_url: str | None = None
    oidc_allowed_email_domains: list[str] = ["wakanow.com"]
    oidc_auto_provision_enabled: bool = False
    oidc_default_role: str = "agent"
    oidc_default_market_id: str | None = None
    oidc_require_email_verified: bool = True
    oidc_http_timeout_seconds: int = 10
    oidc_state_ttl_minutes: int = 10
    allowed_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ]

    model_config = SettingsConfigDict(env_prefix="OMNI_", env_file=".env", extra="ignore")

    @property
    def production_like(self) -> bool:
        return self.environment.lower() in {"staging", "production"}

    def deployment_errors(self, process_name: str) -> list[str]:
        errors: list[str] = []
        if process_name not in {"web", "worker", "release"}:
            errors.append("process_name must be one of: web, worker, release")
        if not self.api_prefix.startswith("/"):
            errors.append("OMNI_API_PREFIX must start with '/'.")
        if self.worker_interval_seconds < 1:
            errors.append("OMNI_WORKER_INTERVAL_SECONDS must be at least 1.")
        if self.worker_outbound_limit < 1:
            errors.append("OMNI_WORKER_OUTBOUND_LIMIT must be at least 1.")
        if self.session_ttl_minutes < 5:
            errors.append("OMNI_SESSION_TTL_MINUTES must be at least 5.")
        if self.webhook_signature_tolerance_seconds < 30:
            errors.append("OMNI_WEBHOOK_SIGNATURE_TOLERANCE_SECONDS must be at least 30.")
        if self.attachment_max_bytes < 1:
            errors.append("OMNI_ATTACHMENT_MAX_BYTES must be at least 1.")
        if self.attachment_storage_backend not in {"local", "s3"}:
            errors.append("OMNI_ATTACHMENT_STORAGE_BACKEND must be one of: local, s3.")
        if self.attachment_storage_backend == "s3":
            if not self.attachment_s3_bucket:
                errors.append("OMNI_ATTACHMENT_S3_BUCKET is required when S3 storage is enabled.")
            if not self.attachment_s3_region and not self.attachment_s3_endpoint_url:
                errors.append(
                    "OMNI_ATTACHMENT_S3_REGION or OMNI_ATTACHMENT_S3_ENDPOINT_URL is required when S3 storage is enabled."
                )
        if self.attachment_s3_access_key_id and not self.attachment_s3_secret_access_key:
            errors.append(
                "OMNI_ATTACHMENT_S3_SECRET_ACCESS_KEY is required when OMNI_ATTACHMENT_S3_ACCESS_KEY_ID is set."
            )
        if self.attachment_s3_secret_access_key and not self.attachment_s3_access_key_id:
            errors.append(
                "OMNI_ATTACHMENT_S3_ACCESS_KEY_ID is required when OMNI_ATTACHMENT_S3_SECRET_ACCESS_KEY is set."
            )
        if self.attachment_scanner_adapter not in {"local", "http"}:
            errors.append("OMNI_ATTACHMENT_SCANNER_ADAPTER must be one of: local, http.")
        if self.attachment_scanner_adapter == "http" and not self.attachment_scanner_http_endpoint:
            errors.append(
                "OMNI_ATTACHMENT_SCANNER_HTTP_ENDPOINT is required when HTTP attachment scanning is enabled."
            )
        if self.attachment_scanner_http_timeout_seconds < 1:
            errors.append("OMNI_ATTACHMENT_SCANNER_HTTP_TIMEOUT_SECONDS must be at least 1.")
        if self.attachment_scanner_http_auth_token and not self.attachment_scanner_http_auth_header:
            errors.append(
                "OMNI_ATTACHMENT_SCANNER_HTTP_AUTH_HEADER is required when scanner auth token is set."
            )
        if self.attachment_download_ttl_minutes < 1:
            errors.append("OMNI_ATTACHMENT_DOWNLOAD_TTL_MINUTES must be at least 1.")
        if self.attachment_retention_days < 30:
            errors.append("OMNI_ATTACHMENT_RETENTION_DAYS must be at least 30.")
        if self.attachment_deleted_retention_days < 1:
            errors.append("OMNI_ATTACHMENT_DELETED_RETENTION_DAYS must be at least 1.")
        if self.attachment_retention_prune_limit < 1:
            errors.append("OMNI_ATTACHMENT_RETENTION_PRUNE_LIMIT must be at least 1.")
        if self.audit_retention_days < 30:
            errors.append("OMNI_AUDIT_RETENTION_DAYS must be at least 30.")
        if self.audit_export_max_rows < 1:
            errors.append("OMNI_AUDIT_EXPORT_MAX_ROWS must be at least 1.")
        if self.ai_provider not in {"auto", "rules", "anthropic"}:
            errors.append("OMNI_AI_PROVIDER must be one of: auto, rules, anthropic.")
        if self.anthropic_timeout_seconds < 1:
            errors.append("OMNI_ANTHROPIC_TIMEOUT_SECONDS must be at least 1.")
        if self.anthropic_max_tokens < 1:
            errors.append("OMNI_ANTHROPIC_MAX_TOKENS must be at least 1.")
        if not self.anthropic_api_base_url:
            errors.append("OMNI_ANTHROPIC_API_BASE_URL must not be empty.")
        if self.ai_provider == "anthropic" and not (
            self.anthropic_api_key or self.anthropic_api_key_file
        ):
            errors.append(
                "OMNI_ANTHROPIC_API_KEY or OMNI_ANTHROPIC_API_KEY_FILE is required when Anthropic is the only AI provider."
            )
        if self.email_smtp_port < 1 or self.email_smtp_port > 65535:
            errors.append("OMNI_EMAIL_SMTP_PORT must be between 1 and 65535.")
        if self.email_smtp_timeout_seconds < 1:
            errors.append("OMNI_EMAIL_SMTP_TIMEOUT_SECONDS must be at least 1.")
        if self.email_smtp_use_ssl and self.email_smtp_use_starttls:
            errors.append("OMNI_EMAIL_SMTP_USE_SSL and OMNI_EMAIL_SMTP_USE_STARTTLS cannot both be true.")
        if self.email_smtp_password and not self.email_smtp_username:
            errors.append("OMNI_EMAIL_SMTP_PASSWORD requires OMNI_EMAIL_SMTP_USERNAME.")
        if (
            self.email_smtp_username
            or self.email_smtp_password
            or self.email_smtp_from_email
        ) and not self.email_smtp_host:
            errors.append("OMNI_EMAIL_SMTP_HOST is required when SMTP identity settings are set.")
        if self.email_imap_port < 1 or self.email_imap_port > 65535:
            errors.append("OMNI_EMAIL_IMAP_PORT must be between 1 and 65535.")
        if self.email_imap_timeout_seconds < 1:
            errors.append("OMNI_EMAIL_IMAP_TIMEOUT_SECONDS must be at least 1.")
        if self.email_imap_fetch_limit < 1:
            errors.append("OMNI_EMAIL_IMAP_FETCH_LIMIT must be at least 1.")
        if self.email_imap_password and not self.email_imap_username:
            errors.append("OMNI_EMAIL_IMAP_PASSWORD requires OMNI_EMAIL_IMAP_USERNAME.")
        if self.email_imap_poll_enabled:
            if not self.email_imap_host:
                errors.append("OMNI_EMAIL_IMAP_HOST is required when inbound email polling is enabled.")
            if not self.email_imap_username:
                errors.append("OMNI_EMAIL_IMAP_USERNAME is required when inbound email polling is enabled.")
            if not self.email_imap_password:
                errors.append("OMNI_EMAIL_IMAP_PASSWORD is required when inbound email polling is enabled.")
        if (
            self.email_imap_username
            or self.email_imap_password
            or self.email_imap_mailbox != "INBOX"
        ) and not self.email_imap_host:
            errors.append("OMNI_EMAIL_IMAP_HOST is required when IMAP identity settings are set.")
        if self.sms_http_timeout_seconds < 1:
            errors.append("OMNI_SMS_HTTP_TIMEOUT_SECONDS must be at least 1.")
        if self.sms_http_endpoint:
            if not self.sms_http_from:
                errors.append("OMNI_SMS_HTTP_FROM is required when SMS HTTP delivery is configured.")
            if not self.sms_http_auth_token:
                errors.append("OMNI_SMS_HTTP_AUTH_TOKEN is required when SMS HTTP delivery is configured.")
        if (self.sms_http_auth_token or self.sms_http_from or self.sms_http_delivery_callback_url) and (
            not self.sms_http_endpoint
        ):
            errors.append("OMNI_SMS_HTTP_ENDPOINT is required when SMS HTTP identity settings are set.")
        if self.sms_http_auth_token and not self.sms_http_auth_header:
            errors.append("OMNI_SMS_HTTP_AUTH_HEADER is required when SMS HTTP auth token is set.")
        if self.voice_http_timeout_seconds < 1:
            errors.append("OMNI_VOICE_HTTP_TIMEOUT_SECONDS must be at least 1.")
        if self.voice_http_endpoint:
            if not self.voice_http_from:
                errors.append("OMNI_VOICE_HTTP_FROM is required when voice HTTP delivery is configured.")
            if not self.voice_http_auth_token:
                errors.append("OMNI_VOICE_HTTP_AUTH_TOKEN is required when voice HTTP delivery is configured.")
        if (
            self.voice_http_auth_token
            or self.voice_http_from
            or self.voice_http_status_callback_url
        ) and not self.voice_http_endpoint:
            errors.append("OMNI_VOICE_HTTP_ENDPOINT is required when voice HTTP identity settings are set.")
        if self.voice_http_auth_token and not self.voice_http_auth_header:
            errors.append("OMNI_VOICE_HTTP_AUTH_HEADER is required when voice HTTP auth token is set.")
        if self.whatsapp_timeout_seconds < 1:
            errors.append("OMNI_WHATSAPP_TIMEOUT_SECONDS must be at least 1.")
        if not self.whatsapp_cloud_api_base_url:
            errors.append("OMNI_WHATSAPP_CLOUD_API_BASE_URL must not be empty.")
        if self.whatsapp_phone_number_id and not self.whatsapp_access_token:
            errors.append("OMNI_WHATSAPP_ACCESS_TOKEN is required when WhatsApp phone number ID is set.")
        if self.whatsapp_access_token and not self.whatsapp_phone_number_id:
            errors.append("OMNI_WHATSAPP_PHONE_NUMBER_ID is required when WhatsApp access token is set.")
        if self.facebook_timeout_seconds < 1:
            errors.append("OMNI_FACEBOOK_TIMEOUT_SECONDS must be at least 1.")
        if not self.facebook_graph_api_base_url:
            errors.append("OMNI_FACEBOOK_GRAPH_API_BASE_URL must not be empty.")
        if self.facebook_page_id and not self.facebook_page_access_token:
            errors.append("OMNI_FACEBOOK_PAGE_ACCESS_TOKEN is required when Facebook page ID is set.")
        if self.facebook_page_access_token and not self.facebook_page_id:
            errors.append("OMNI_FACEBOOK_PAGE_ID is required when Facebook page access token is set.")
        if self.facebook_messaging_type not in {"RESPONSE", "UPDATE", "MESSAGE_TAG"}:
            errors.append("OMNI_FACEBOOK_MESSAGING_TYPE must be RESPONSE, UPDATE, or MESSAGE_TAG.")
        if self.instagram_timeout_seconds < 1:
            errors.append("OMNI_INSTAGRAM_TIMEOUT_SECONDS must be at least 1.")
        if not self.instagram_graph_api_base_url:
            errors.append("OMNI_INSTAGRAM_GRAPH_API_BASE_URL must not be empty.")
        if self.instagram_business_account_id and not self.instagram_access_token:
            errors.append(
                "OMNI_INSTAGRAM_ACCESS_TOKEN is required when Instagram business account ID is set."
            )
        if self.instagram_access_token and not self.instagram_business_account_id:
            errors.append(
                "OMNI_INSTAGRAM_BUSINESS_ACCOUNT_ID is required when Instagram access token is set."
            )
        if self.alert_webhook_timeout_seconds < 1:
            errors.append("OMNI_ALERT_WEBHOOK_TIMEOUT_SECONDS must be at least 1.")
        if self.alert_delivery_max_attempts < 1:
            errors.append("OMNI_ALERT_DELIVERY_MAX_ATTEMPTS must be at least 1.")
        if self.alert_delivery_retry_minutes < 1:
            errors.append("OMNI_ALERT_DELIVERY_RETRY_MINUTES must be at least 1.")
        if self.alert_delivery_min_severity not in {"info", "warning", "critical"}:
            errors.append("OMNI_ALERT_DELIVERY_MIN_SEVERITY must be info, warning, or critical.")
        if self.alert_webhook_secret and not self.alert_webhook_url:
            errors.append("OMNI_ALERT_WEBHOOK_SECRET requires OMNI_ALERT_WEBHOOK_URL.")
        if self.oidc_http_timeout_seconds < 1:
            errors.append("OMNI_OIDC_HTTP_TIMEOUT_SECONDS must be at least 1.")
        if self.oidc_state_ttl_minutes < 1:
            errors.append("OMNI_OIDC_STATE_TTL_MINUTES must be at least 1.")
        if self.oidc_default_role not in {"agent", "supervisor", "admin", "auditor", "service_account"}:
            errors.append("OMNI_OIDC_DEFAULT_ROLE must be a valid Omni user role.")
        if self.oidc_auto_provision_enabled and not self.oidc_default_market_id:
            errors.append(
                "OMNI_OIDC_DEFAULT_MARKET_ID is required when OIDC auto-provisioning is enabled."
            )
        oidc_required = {
            "OMNI_OIDC_AUTHORIZATION_URL": self.oidc_authorization_url,
            "OMNI_OIDC_TOKEN_URL": self.oidc_token_url,
            "OMNI_OIDC_USERINFO_URL": self.oidc_userinfo_url,
            "OMNI_OIDC_CLIENT_ID": self.oidc_client_id,
            "OMNI_OIDC_CLIENT_SECRET": self.oidc_client_secret,
            "OMNI_OIDC_REDIRECT_URL": self.oidc_redirect_url,
        }
        if self.oidc_enabled:
            for field_name, field_value in oidc_required.items():
                if not field_value:
                    errors.append(f"{field_name} is required when OIDC login is enabled.")
        if any(oidc_required.values()) and not self.oidc_enabled:
            errors.append("OMNI_OIDC_ENABLED=true is required when OIDC identity settings are set.")
        if self.production_like and self.oidc_enabled:
            oidc_urls = {
                "OMNI_OIDC_AUTHORIZATION_URL": self.oidc_authorization_url,
                "OMNI_OIDC_TOKEN_URL": self.oidc_token_url,
                "OMNI_OIDC_USERINFO_URL": self.oidc_userinfo_url,
                "OMNI_OIDC_REDIRECT_URL": self.oidc_redirect_url,
            }
            for oidc_field_name, oidc_field_value in oidc_urls.items():
                if oidc_field_value and not oidc_field_value.startswith("https://"):
                    errors.append(f"{oidc_field_name} must use HTTPS in staging/production.")
        if self.production_like and self.ai_provider in {"auto", "anthropic"}:
            if self.anthropic_api_base_url and not self.anthropic_api_base_url.startswith("https://"):
                errors.append("OMNI_ANTHROPIC_API_BASE_URL must use HTTPS in staging/production.")
        rate_limit_fields = {
            "OMNI_LOGIN_RATE_LIMIT_ATTEMPTS": self.login_rate_limit_attempts,
            "OMNI_LOGIN_RATE_LIMIT_WINDOW_SECONDS": self.login_rate_limit_window_seconds,
            "OMNI_CONNECTOR_INBOUND_RATE_LIMIT_ATTEMPTS": self.connector_inbound_rate_limit_attempts,
            "OMNI_CONNECTOR_INBOUND_RATE_LIMIT_WINDOW_SECONDS": self.connector_inbound_rate_limit_window_seconds,
            "OMNI_WEBHOOK_RATE_LIMIT_ATTEMPTS": self.webhook_rate_limit_attempts,
            "OMNI_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS": self.webhook_rate_limit_window_seconds,
            "OMNI_PORTAL_RATE_LIMIT_ATTEMPTS": self.portal_rate_limit_attempts,
            "OMNI_PORTAL_RATE_LIMIT_WINDOW_SECONDS": self.portal_rate_limit_window_seconds,
        }
        for rate_limit_field_name, rate_limit_field_value in rate_limit_fields.items():
            if rate_limit_field_value < 1:
                errors.append(f"{rate_limit_field_name} must be at least 1.")
        if self.production_like:
            if self.session_secret == "omni-ticket-local-dev-secret":
                errors.append("OMNI_SESSION_SECRET must be set in staging/production.")
            if self.database_url.startswith("sqlite"):
                errors.append("OMNI_DATABASE_URL must point to PostgreSQL in staging/production.")
            if self.initialize_database:
                errors.append("OMNI_INITIALIZE_DATABASE must be false in staging/production; run migrations explicitly.")
            if not self.allowed_origins:
                errors.append("OMNI_ALLOWED_ORIGINS must include the deployed frontend origin.")
            if "*" in self.allowed_origins:
                errors.append("OMNI_ALLOWED_ORIGINS cannot contain '*' in staging/production.")
            if self.outbound_local_adapter_enabled:
                errors.append("OMNI_OUTBOUND_LOCAL_ADAPTER_ENABLED must be false in staging/production.")
        return errors

    def validate_for_process(self, process_name: str) -> None:
        errors = self.deployment_errors(process_name)
        if errors:
            raise RuntimeError("Invalid Omni Ticket runtime configuration: " + " ".join(errors))


settings = Settings()
