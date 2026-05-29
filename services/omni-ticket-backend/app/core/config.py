from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Omni Ticket Backend"
    environment: str = "local"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/omni-ticket.db"
    database_echo: bool = False
    initialize_database: bool = True
    worker_interval_seconds: int = 60
    worker_outbound_limit: int = 50
    session_secret: str = "omni-ticket-local-dev-secret"
    session_ttl_minutes: int = 8 * 60
    webhook_signature_tolerance_seconds: int = 5 * 60
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_seconds: int = 60
    connector_inbound_rate_limit_attempts: int = 120
    connector_inbound_rate_limit_window_seconds: int = 60
    webhook_rate_limit_attempts: int = 120
    webhook_rate_limit_window_seconds: int = 60
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
        rate_limit_fields = {
            "OMNI_LOGIN_RATE_LIMIT_ATTEMPTS": self.login_rate_limit_attempts,
            "OMNI_LOGIN_RATE_LIMIT_WINDOW_SECONDS": self.login_rate_limit_window_seconds,
            "OMNI_CONNECTOR_INBOUND_RATE_LIMIT_ATTEMPTS": self.connector_inbound_rate_limit_attempts,
            "OMNI_CONNECTOR_INBOUND_RATE_LIMIT_WINDOW_SECONDS": self.connector_inbound_rate_limit_window_seconds,
            "OMNI_WEBHOOK_RATE_LIMIT_ATTEMPTS": self.webhook_rate_limit_attempts,
            "OMNI_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS": self.webhook_rate_limit_window_seconds,
        }
        for field_name, field_value in rate_limit_fields.items():
            if field_value < 1:
                errors.append(f"{field_name} must be at least 1.")
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
        return errors

    def validate_for_process(self, process_name: str) -> None:
        errors = self.deployment_errors(process_name)
        if errors:
            raise RuntimeError("Invalid Omni Ticket runtime configuration: " + " ".join(errors))


settings = Settings()
