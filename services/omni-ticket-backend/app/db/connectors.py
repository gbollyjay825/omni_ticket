from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import audit_event_from_record, connector_account_from_record
from app.db.models import AuditEventRecord, ConnectorAccountRecord, ConnectorEventRecord
from app.models.domain import (
    ChannelType,
    ConnectorAccount,
    CreateConnectorAccountRequest,
    UpdateConnectorAccountRequest,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _audit(
    db: Session,
    state: InMemoryStore,
    *,
    action: str,
    entity_id: str,
    market_id: str,
    details: dict,
) -> None:
    record = AuditEventRecord(
        id=_new_id("audit"),
        actor="connector-admin",
        action=action,
        entity_type="connector_account",
        entity_id=entity_id,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    state.audit.append(audit_event_from_record(record))


class ConnectorAccountRepository:
    def get_account_for_provider(
        self,
        db: Session,
        *,
        market_id: str,
        provider: ChannelType,
    ) -> ConnectorAccountRecord | None:
        return db.scalar(
            select(ConnectorAccountRecord).where(
                ConnectorAccountRecord.market_id == market_id,
                ConnectorAccountRecord.provider == provider.value,
            )
        )

    def delivery_id_seen(
        self,
        db: Session,
        *,
        market_id: str,
        provider: ChannelType,
        delivery_id: str,
    ) -> bool:
        records = db.scalars(
            select(ConnectorEventRecord).where(
                ConnectorEventRecord.market_id == market_id,
                ConnectorEventRecord.provider == provider.value,
            )
        ).all()
        return any(
            (record.payload or {}).get("metadata", {}).get("webhook_delivery_id") == delivery_id
            for record in records
        )

    def external_event_seen(
        self,
        db: Session,
        *,
        market_id: str,
        provider: ChannelType,
        external_id: str,
    ) -> bool:
        return (
            db.scalar(
                select(ConnectorEventRecord).where(
                    ConnectorEventRecord.market_id == market_id,
                    ConnectorEventRecord.provider == provider.value,
                    ConnectorEventRecord.external_id == external_id,
                )
            )
            is not None
        )

    def record_webhook_failure(
        self,
        db: Session,
        state: InMemoryStore,
        *,
        account: ConnectorAccountRecord,
        error: str,
        delivery_id: str | None = None,
    ) -> ConnectorAccount:
        account.failure_count = (account.failure_count or 0) + 1
        account.last_error = error
        _audit(
            db,
            state,
            action="connector.webhook_rejected",
            entity_id=account.id,
            market_id=account.market_id,
            details={
                "provider": account.provider,
                "delivery_id": delivery_id,
                "error": error,
            },
        )
        db.commit()
        db.refresh(account)
        return connector_account_from_record(account)

    def record_webhook_success(
        self,
        db: Session,
        *,
        account: ConnectorAccountRecord,
    ) -> None:
        account.last_error = None
        db.flush()

    def list_accounts(
        self,
        db: Session,
        market_id: str,
    ) -> list[ConnectorAccount]:
        return [
            connector_account_from_record(record)
            for record in db.scalars(
                select(ConnectorAccountRecord)
                .where(ConnectorAccountRecord.market_id == market_id)
                .order_by(ConnectorAccountRecord.provider.asc())
            ).all()
        ]

    def create_account(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateConnectorAccountRequest,
        market_id: str,
    ) -> ConnectorAccount:
        existing = db.scalar(
            select(ConnectorAccountRecord).where(
                ConnectorAccountRecord.market_id == market_id,
                ConnectorAccountRecord.provider == request.provider.value,
            )
        )
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Connector account already exists for this market and provider",
            )
        payload = request.model_dump(mode="json")
        payload["market_id"] = market_id
        record = ConnectorAccountRecord(id=_new_id("connector_account"), **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            action="connector_account.create",
            entity_id=record.id,
            market_id=market_id,
            details={"provider": request.provider.value, "status": request.status.value},
        )
        db.commit()
        db.refresh(record)
        return connector_account_from_record(record)

    def update_account(
        self,
        db: Session,
        state: InMemoryStore,
        account_id: str,
        request: UpdateConnectorAccountRequest,
        market_id: str,
    ) -> ConnectorAccount:
        record = db.get(ConnectorAccountRecord, account_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Connector account not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        for key, value in patch.items():
            if value is not None:
                setattr(record, key, value)
        _audit(
            db,
            state,
            action="connector_account.update",
            entity_id=account_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        return connector_account_from_record(record)


connector_account_repository = ConnectorAccountRepository()
