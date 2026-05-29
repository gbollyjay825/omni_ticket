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


def test_validate_for_process_raises_for_invalid_production_config() -> None:
    settings = Settings(environment="production", database_url="sqlite:///./data/test.db")

    with pytest.raises(RuntimeError):
        settings.validate_for_process("worker")


def test_rate_limit_settings_must_be_positive() -> None:
    settings = Settings(
        login_rate_limit_attempts=0,
        connector_inbound_rate_limit_window_seconds=0,
        webhook_rate_limit_attempts=0,
    )

    errors = settings.deployment_errors("web")

    assert any("OMNI_LOGIN_RATE_LIMIT_ATTEMPTS" in error for error in errors)
    assert any("OMNI_CONNECTOR_INBOUND_RATE_LIMIT_WINDOW_SECONDS" in error for error in errors)
    assert any("OMNI_WEBHOOK_RATE_LIMIT_ATTEMPTS" in error for error in errors)
