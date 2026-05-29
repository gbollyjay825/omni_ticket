from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _prepare_sqlite_path(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path in {":memory:", ""}:
        return
    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


def create_database_engine(database_url: str | None = None) -> Engine:
    url = database_url or settings.database_url
    _prepare_sqlite_path(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=settings.database_echo, future=True, connect_args=connect_args)


engine = create_database_engine()
SessionLocal = sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)
SessionLocal.configure(bind=engine)


def get_engine() -> Engine:
    return engine


def configure_database(database_url: str | None = None) -> Engine:
    global engine

    current_engine = engine
    next_engine = create_database_engine(database_url)
    SessionLocal.configure(bind=next_engine)
    engine = next_engine
    current_engine.dispose()
    return engine


def get_db() -> Generator[Session]:
    with SessionLocal() as session:
        yield session
