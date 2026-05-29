from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.store import store
from app.db.bootstrap import seed_reference_data
from app.db.models import Base
from app.db.session import engine
from app.main import create_app
from app.models.domain import WorkspaceSettings


@pytest.fixture(autouse=True)
def reset_store() -> Generator[None]:
    reset_local_state()
    yield
    reset_local_state()


def reset_local_state() -> None:
    store.settings = WorkspaceSettings()
    store.seed()
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
def login_as() -> Callable[[str, str], dict[str, str]]:
    def _login(email: str, market_id: str = "market-ng") -> dict[str, str]:
        test_client = TestClient(create_app())
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "omni-demo", "market_id": market_id},
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "X-Omni-Market": market_id}

    return _login
