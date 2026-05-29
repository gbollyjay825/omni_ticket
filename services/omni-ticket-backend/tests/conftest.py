from collections.abc import Generator
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.store import store
from app.db.bootstrap import seed_reference_data
from app.db.models import Base
from app.db.session import configure_database, get_engine
from app.main import create_app
from app.models.domain import WorkspaceSettings


@pytest.fixture(scope="session", autouse=True)
def isolated_database(tmp_path_factory: pytest.TempPathFactory) -> Generator[None]:
    database_path = tmp_path_factory.mktemp("db") / "omni-ticket-tests.db"
    original_database_url = str(get_engine().url)
    configure_database(f"sqlite:///{database_path}")
    try:
        yield
    finally:
        configure_database(original_database_url)


@pytest.fixture(autouse=True)
def reset_store() -> Generator[None]:
    reset_local_state()
    yield
    reset_local_state()


def reset_local_state() -> None:
    store.settings = WorkspaceSettings()
    store.seed()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        seed_reference_data(session, store)


@pytest.fixture
def client() -> TestClient:
    test_client = TestClient(create_app())
    response = test_client.post(
        "/api/v1/auth/login",
        json={"email": "gbolahan@omniticket.example.com", "password": "omni-demo"},
    )
    token = response.json()["access_token"]
    test_client.headers.update(
        {"Authorization": f"Bearer {token}", "X-Omni-Market": "market-ng"}
    )
    return test_client


@pytest.fixture
def login_as() -> Callable[..., dict[str, str]]:
    def _login(
        email: str,
        market_id: str = "market-ng",
        password: str = "omni-demo",
    ) -> dict[str, str]:
        test_client = TestClient(create_app())
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password, "market_id": market_id},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "X-Omni-Market": market_id}

    return _login
