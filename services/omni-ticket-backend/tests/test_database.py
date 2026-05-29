from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import store
from app.db.bootstrap import create_schema, seed_reference_data, table_names
from app.db.models import CustomerRecord, MarketRecord, TicketRecord, UserRecord
from app.db.session import create_database_engine


def test_database_schema_and_seed_are_postgres_ready_with_local_sqlite(tmp_path: Path) -> None:
    database_path = tmp_path / "omni-ticket-test.db"
    engine = create_database_engine(f"sqlite:///{database_path}")

    create_schema(engine)
    tables = table_names(engine)

    assert "markets" in tables
    assert "users" in tables
    assert "tickets" in tables
    assert "customers" in tables
    assert "attachments" in tables
    assert "connector_events" in tables
    assert "audit_events" in tables

    with Session(engine) as session:
        seed_reference_data(session, store)

        markets = session.scalars(select(MarketRecord)).all()
        users = session.scalars(select(UserRecord)).all()
        nigeria_customers = session.scalars(
            select(CustomerRecord).where(CustomerRecord.market_id == "market-ng")
        ).all()
        ghana_tickets = session.scalars(
            select(TicketRecord).where(TicketRecord.market_id == "market-gh")
        ).all()

        assert {market.id for market in markets} >= {"market-ng", "market-gh", "market-uk"}
        assert any(user.email == "gbolahan@omniticket.example.com" for user in users)
        assert all(customer.market_id == "market-ng" for customer in nigeria_customers)
        assert len(ghana_tickets) == 1
