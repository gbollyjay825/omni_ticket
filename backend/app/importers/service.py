from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
import csv
from datetime import datetime, timedelta, timezone
import gzip
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.imports import import_repository
from app.db.models import (
    CaseRecord,
    ChatConversationRecord,
    ChatMessageRecord,
    ChatParticipantRecord,
    CustomerIdentityRecord,
    CustomerRecord,
    ImportRunRecord,
    TicketRecord,
    TimelineEventRecord,
)
from app.db.realtime import realtime_event_repository
from app.importers.clients import FreshchatClient, FreshdeskClient
from app.models.domain import utc_now


class ImportDataError(RuntimeError):
    pass


_ACTIVE_TICKET_STATUSES = {"open", "pending", "waiting"}
_HTML_TAG = re.compile(r"<[^>]+>")

_FRESHDESK_STATUS = {
    2: "open",
    3: "pending",
    4: "solved",
    5: "closed",
}
_FRESHDESK_PRIORITY = {1: "low", 2: "normal", 3: "high", 4: "urgent"}
_FRESHDESK_CHANNEL = {
    1: "email",
    2: "portal",
    3: "voice",
    4: "api",
    5: "api",
    6: "chat",
    7: "chat",
    8: "api",
    9: "portal",
    10: "email",
}


def _stable_id(prefix: str, provider: str, entity_type: str, external_id: object) -> str:
    value = uuid5(NAMESPACE_URL, f"omni:{provider}:{entity_type}:{external_id}").hex
    return f"{prefix}_{value}"


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def _datetime(value: object, *, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ImportDataError(f"Invalid source timestamp: {value}") from exc
    else:
        parsed = fallback or utc_now()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _source_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    return _datetime(value)


def _plain_text(value: object) -> str:
    text = unescape(_HTML_TAG.sub(" ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _decoded_json(value: object) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _list_value(value: object) -> list[Any]:
    decoded = _decoded_json(value)
    if isinstance(decoded, list):
        return decoded
    if decoded in (None, ""):
        return []
    if isinstance(decoded, str):
        return [item.strip() for item in decoded.split(",") if item.strip()]
    return [decoded]


def _mapping_value(value: object) -> dict[str, Any]:
    decoded = _decoded_json(value)
    return dict(decoded) if isinstance(decoded, dict) else {}


def _normalized_email(value: object) -> str:
    return str(value or "").strip().lower()


def _normalized_phone(value: object) -> str:
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    return f"+{digits}"


def _freshchat_message_body(payload: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    text_parts: list[str] = []
    media_parts: list[dict[str, Any]] = []
    parts = _decoded_json(payload.get("message_parts"))
    if isinstance(parts, list):
        for part in parts:
            if not isinstance(part, dict):
                continue
            text_part = part.get("text")
            if isinstance(text_part, dict) and text_part.get("content"):
                text_parts.append(_plain_text(text_part["content"]))
            elif isinstance(text_part, str):
                text_parts.append(_plain_text(text_part))
            for key in ("image", "file", "audio", "video"):
                media = part.get(key)
                if isinstance(media, dict):
                    media_parts.append({"type": key, **media})
    if not text_parts:
        fallback = payload.get("body") or payload.get("content") or payload.get("text")
        if isinstance(fallback, dict):
            fallback = fallback.get("content")
        if fallback:
            text_parts.append(_plain_text(fallback))
    return "\n".join(part for part in text_parts if part), media_parts


def iter_export_records(path: Path, *, collection_key: str | None = None) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        raise ImportDataError(f"Export file does not exist: {path}")
    compressed = path.suffix.lower() == ".gz"
    logical_suffix = path.with_suffix("").suffix.lower() if compressed else path.suffix.lower()
    open_text: Callable[..., Any] = gzip.open if compressed else open
    if logical_suffix in {".jsonl", ".ndjson"}:
        with open_text(path, "rt", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ImportDataError(
                        f"Invalid JSON on line {line_number} of {path.name}"
                    ) from exc
                if not isinstance(payload, dict):
                    raise ImportDataError(
                        f"Expected an object on line {line_number} of {path.name}"
                    )
                yield dict(payload)
        return
    if logical_suffix == ".csv":
        with open_text(path, "rt", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                yield dict(row)
        return
    if logical_suffix != ".json":
        raise ImportDataError(f"Unsupported export format for {path.name}")
    with open_text(path, "rt", encoding="utf-8-sig") as handle:
        try:
            payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ImportDataError(f"Invalid JSON export: {path.name}") from exc
    records: object = payload
    if isinstance(payload, dict):
        if collection_key and collection_key in payload:
            records = payload[collection_key]
        else:
            list_values = [value for value in payload.values() if isinstance(value, list)]
            if len(list_values) == 1:
                records = list_values[0]
            else:
                records = [payload]
    if not isinstance(records, list):
        raise ImportDataError(f"Expected a JSON array in {path.name}")
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ImportDataError(f"Expected an object at record {index} of {path.name}")
        yield dict(record)


class ImportStatistics:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def mark(self, resource: str, outcome: str) -> None:
        key = f"{resource}_{outcome}"
        self.values[key] = self.values.get(key, 0) + 1

    def payload(self) -> dict[str, int]:
        return dict(sorted(self.values.items()))


class FreshworksImportService:
    def _identity_customer(
        self,
        db: Session,
        *,
        market_id: str,
        identity_type: str,
        normalized_value: str,
    ) -> CustomerRecord | None:
        if not normalized_value:
            return None
        identity = db.scalar(
            select(CustomerIdentityRecord).where(
                CustomerIdentityRecord.market_id == market_id,
                CustomerIdentityRecord.provider == "global",
                CustomerIdentityRecord.identity_type == identity_type,
                CustomerIdentityRecord.normalized_value == normalized_value,
            )
        )
        return db.get(CustomerRecord, identity.customer_id) if identity else None

    def _set_identity(
        self,
        db: Session,
        *,
        market_id: str,
        customer_id: str,
        provider: str,
        identity_type: str,
        value: object,
        verified: bool,
        primary: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        display_value = str(value or "").strip()
        normalized_value = (
            _normalized_email(display_value)
            if identity_type == "email"
            else _normalized_phone(display_value)
            if identity_type == "phone"
            else display_value.lower()
        )
        if not normalized_value:
            return
        record = db.scalar(
            select(CustomerIdentityRecord).where(
                CustomerIdentityRecord.market_id == market_id,
                CustomerIdentityRecord.provider == provider,
                CustomerIdentityRecord.identity_type == identity_type,
                CustomerIdentityRecord.normalized_value == normalized_value,
            )
        )
        if record is None:
            record = CustomerIdentityRecord(
                id=_stable_id(
                    "identity",
                    provider,
                    identity_type,
                    f"{market_id}:{normalized_value}",
                ),
                market_id=market_id,
                customer_id=customer_id,
                provider=provider,
                identity_type=identity_type,
                normalized_value=normalized_value,
                display_value=display_value,
                verified=verified,
                primary=primary,
                identity_metadata=dict(metadata or {}),
            )
            db.add(record)
        elif record.customer_id != customer_id:
            raise ImportDataError(
                f"Identity {identity_type}:{normalized_value} is already assigned to another customer"
            )
        else:
            record.display_value = display_value or record.display_value
            record.verified = record.verified or verified
            record.primary = record.primary or primary
            record.identity_metadata = {**(record.identity_metadata or {}), **dict(metadata or {})}
            record.updated_at = utc_now()

    def upsert_freshdesk_contact(
        self,
        db: Session,
        *,
        market_id: str,
        payload: Mapping[str, Any],
        statistics: ImportStatistics,
    ) -> CustomerRecord:
        external_id = payload.get("id")
        if external_id is None:
            raise ImportDataError("Freshdesk contact is missing id")
        digest = _payload_hash(payload)
        mapping = import_repository.get_mapping(
            db,
            market_id=market_id,
            provider="freshdesk",
            entity_type="contact",
            external_id=external_id,
        )
        if mapping and mapping.payload_hash == digest:
            existing = db.get(CustomerRecord, mapping.internal_id)
            if existing is not None:
                statistics.mark("contacts", "unchanged")
                return existing

        email = _normalized_email(payload.get("email"))
        if not email:
            other_emails = _list_value(payload.get("other_emails"))
            if other_emails:
                email = _normalized_email(other_emails[0])
        phones = [
            phone
            for phone in (
                _normalized_phone(payload.get("mobile")),
                _normalized_phone(payload.get("phone")),
            )
            if phone
        ]
        customer = db.get(CustomerRecord, mapping.internal_id) if mapping else None
        if customer is None and email:
            customer = db.scalar(
                select(CustomerRecord).where(
                    CustomerRecord.market_id == market_id,
                    CustomerRecord.email == email,
                )
            ) or self._identity_customer(
                db,
                market_id=market_id,
                identity_type="email",
                normalized_value=email,
            )
        if customer is None:
            for phone in phones:
                customer = self._identity_customer(
                    db,
                    market_id=market_id,
                    identity_type="phone",
                    normalized_value=phone,
                )
                if customer:
                    break

        created = customer is None
        if customer is None:
            customer = CustomerRecord(
                id=_stable_id("customer", "freshdesk", "contact", external_id),
                market_id=market_id,
                name=str(payload.get("name") or f"Freshdesk contact {external_id}").strip(),
                email=email or f"no-email+freshdesk-{external_id}@identity.omni.invalid",
                location=str(payload.get("address") or "").strip(),
                preferred_channels=["email"] if email else [],
                contact_points=[],
                tags=sorted({"freshdesk-import", *[str(tag) for tag in _list_value(payload.get("tags"))]}),
                notes=_plain_text(payload.get("description")),
                created_at=_datetime(payload.get("created_at")),
                updated_at=_datetime(payload.get("updated_at")),
            )
            db.add(customer)
        else:
            customer.name = str(payload.get("name") or customer.name).strip()
            if email and customer.email.endswith("@identity.omni.invalid"):
                customer.email = email
            customer.location = str(payload.get("address") or customer.location).strip()
            customer.tags = sorted(
                set(customer.tags or [])
                | {"freshdesk-import"}
                | {str(tag) for tag in _list_value(payload.get("tags"))}
            )
            customer.notes = _plain_text(payload.get("description")) or customer.notes
            customer.updated_at = _datetime(payload.get("updated_at"))

        points = list(customer.contact_points or [])
        source_points: list[dict[str, Any]] = []
        if email:
            source_points.append({"channel": "email", "value": email, "verified": True})
        for phone in phones:
            source_points.append({"channel": "voice", "value": phone, "verified": True})
        for point in source_points:
            if not any(
                item.get("channel") == point["channel"] and item.get("value") == point["value"]
                for item in points
            ):
                points.append(point)
        customer.contact_points = points
        if email:
            self._set_identity(
                db,
                market_id=market_id,
                customer_id=customer.id,
                provider="global",
                identity_type="email",
                value=email,
                verified=True,
                primary=True,
            )
        for phone in phones:
            self._set_identity(
                db,
                market_id=market_id,
                customer_id=customer.id,
                provider="global",
                identity_type="phone",
                value=phone,
                verified=True,
            )
        self._set_identity(
            db,
            market_id=market_id,
            customer_id=customer.id,
            provider="freshdesk",
            identity_type="external_id",
            value=external_id,
            verified=True,
            metadata={"source": "contact"},
        )
        db.flush()
        import_repository.set_mapping(
            db,
            market_id=market_id,
            provider="freshdesk",
            entity_type="contact",
            external_id=external_id,
            internal_id=customer.id,
            source_updated_at=_source_datetime(payload.get("updated_at")),
            payload_hash=digest,
        )
        statistics.mark("contacts", "created" if created else "updated")
        return customer

    def _ticket_customer(
        self,
        db: Session,
        *,
        market_id: str,
        payload: Mapping[str, Any],
        client: FreshdeskClient | None,
        statistics: ImportStatistics,
    ) -> CustomerRecord:
        requester_id = payload.get("requester_id")
        mapping = (
            import_repository.get_mapping(
                db,
                market_id=market_id,
                provider="freshdesk",
                entity_type="contact",
                external_id=requester_id,
            )
            if requester_id is not None
            else None
        )
        customer = db.get(CustomerRecord, mapping.internal_id) if mapping else None
        if customer is not None:
            return customer
        embedded = payload.get("requester")
        if isinstance(embedded, dict):
            contact_payload = {**embedded, "id": requester_id or embedded.get("id")}
        elif requester_id is not None and client is not None:
            contact_payload = client.get_contact(requester_id)
        else:
            raise ImportDataError(f"Freshdesk ticket {payload.get('id')} has no requester")
        return self.upsert_freshdesk_contact(
            db,
            market_id=market_id,
            payload=contact_payload,
            statistics=statistics,
        )

    def _case_for_ticket(
        self,
        db: Session,
        *,
        market_id: str,
        customer_id: str,
        external_id: object,
        subject: str,
        description: str,
        priority: str,
        status: str,
        created_at: datetime,
        updated_at: datetime,
    ) -> CaseRecord:
        if status in _ACTIVE_TICKET_STATUSES:
            case = db.scalar(
                select(CaseRecord).where(
                    CaseRecord.market_id == market_id,
                    CaseRecord.customer_id == customer_id,
                    CaseRecord.status == "open",
                )
            )
            if case is not None:
                return case
            case_status = "open"
            case_id = _stable_id("case", "freshdesk", "active_customer", customer_id)
            public_id = f"FDC-{str(external_id)[:30]}"
            previous = db.get(CaseRecord, case_id)
            if previous is not None:
                previous.status = "open"
                previous.title = subject[:255]
                previous.priority = priority
                previous.summary = description
                previous.updated_at = updated_at
                return previous
        else:
            case_status = "closed"
            case_id = _stable_id("case", "freshdesk", "ticket", external_id)
            case = db.get(CaseRecord, case_id)
            if case is not None:
                return case
            public_id = f"FDC-{str(external_id)[:30]}"
        case = CaseRecord(
            id=case_id,
            market_id=market_id,
            public_id=public_id,
            customer_id=customer_id,
            title=subject[:255],
            status=case_status,
            priority=priority,
            summary=description,
            opened_by="Freshdesk import",
            created_at=created_at,
            updated_at=updated_at,
        )
        db.add(case)
        db.flush()
        return case

    def upsert_freshdesk_ticket(
        self,
        db: Session,
        *,
        market_id: str,
        payload: Mapping[str, Any],
        client: FreshdeskClient | None,
        statistics: ImportStatistics,
    ) -> TicketRecord:
        external_id = payload.get("id")
        if external_id is None:
            raise ImportDataError("Freshdesk ticket is missing id")
        customer = self._ticket_customer(
            db,
            market_id=market_id,
            payload=payload,
            client=client,
            statistics=statistics,
        )
        digest = _payload_hash(payload)
        mapping = import_repository.get_mapping(
            db,
            market_id=market_id,
            provider="freshdesk",
            entity_type="ticket",
            external_id=external_id,
        )
        unchanged = bool(mapping and mapping.payload_hash == digest)
        ticket = db.get(TicketRecord, mapping.internal_id) if mapping else None
        created = ticket is None
        status = _FRESHDESK_STATUS.get(int(payload.get("status") or 2), "open")
        priority = _FRESHDESK_PRIORITY.get(int(payload.get("priority") or 2), "normal")
        channel = _FRESHDESK_CHANNEL.get(int(payload.get("source") or 1), "api")
        subject = str(payload.get("subject") or f"Freshdesk ticket {external_id}").strip()
        description = _plain_text(payload.get("description_text") or payload.get("description"))
        created_at = _datetime(payload.get("created_at"))
        updated_at = _datetime(payload.get("updated_at"), fallback=created_at)
        resolved_at = _source_datetime(
            payload.get("resolved_at") or (updated_at if status == "solved" else None)
        )
        closed_at = _source_datetime(
            payload.get("closed_at") or (updated_at if status == "closed" else None)
        )
        due_at = _datetime(payload.get("due_by"), fallback=created_at + timedelta(days=1))
        first_response_due_at = _datetime(
            payload.get("fr_due_by"), fallback=created_at + timedelta(hours=2)
        )
        case = self._case_for_ticket(
            db,
            market_id=market_id,
            customer_id=customer.id,
            external_id=external_id,
            subject=subject,
            description=description,
            priority=priority,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
        )
        source_fields = _mapping_value(payload.get("custom_fields"))
        source_fields["freshdesk"] = {
            "ticket_id": str(external_id),
            "requester_id": payload.get("requester_id"),
            "responder_id": payload.get("responder_id"),
            "group_id": payload.get("group_id"),
            "product_id": payload.get("product_id"),
            "source": payload.get("source"),
            "status": payload.get("status"),
            "priority": payload.get("priority"),
        }
        sla_met = None
        terminal_at = closed_at or resolved_at
        if terminal_at:
            sla_met = terminal_at <= due_at
        values = {
            "market_id": market_id,
            "public_id": f"FD-{external_id}",
            "subject": subject[:255],
            "description": description,
            "customer_id": customer.id,
            "channel": channel,
            "status": status,
            "priority": priority,
            "sentiment": "neutral",
            "assignee_id": None,
            "team": (
                f"Freshdesk group {payload.get('group_id')}"
                if payload.get("group_id") is not None
                else "Unassigned"
            ),
            "tags": sorted(
                {"freshdesk-import", *[str(tag) for tag in _list_value(payload.get("tags"))]}
            ),
            "custom_fields": source_fields,
            "tasks": [],
            "sla": {
                "first_response_due_at": first_response_due_at.isoformat(),
                "resolution_due_at": due_at.isoformat(),
                "risk": "breached" if due_at < utc_now() and status in _ACTIVE_TICKET_STATUSES else "on_track",
                "breached": bool(due_at < utc_now() and status in _ACTIVE_TICKET_STATUSES),
            },
            "ai_summary": "",
            "recommended_action": "",
            "case_id": case.id,
            "resolved_at": resolved_at,
            "closed_at": closed_at,
            "sla_resolution_met": sla_met,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        if ticket is None:
            ticket = TicketRecord(
                id=_stable_id("ticket", "freshdesk", "ticket", external_id),
                **values,
            )
            db.add(ticket)
            if description:
                db.add(
                    TimelineEventRecord(
                        id=_stable_id("timeline", "freshdesk", "ticket_description", external_id),
                        market_id=market_id,
                        ticket_id=ticket.id,
                        type="inbound",
                        channel=channel,
                        actor=customer.name,
                        body=description,
                        public=True,
                        event_metadata={
                            "provider": "freshdesk",
                            "external_ticket_id": str(external_id),
                            "source_kind": "ticket_description",
                        },
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
        elif mapping and mapping.payload_hash != digest:
            for key, value in values.items():
                setattr(ticket, key, value)
        db.flush()
        import_repository.set_mapping(
            db,
            market_id=market_id,
            provider="freshdesk",
            entity_type="ticket",
            external_id=external_id,
            internal_id=ticket.id,
            source_updated_at=updated_at,
            payload_hash=digest,
            metadata={"public_id": ticket.public_id},
        )
        statistics.mark(
            "tickets",
            "created" if created else "unchanged" if unchanged else "updated",
        )
        return ticket

    def upsert_freshdesk_conversation(
        self,
        db: Session,
        *,
        market_id: str,
        ticket: TicketRecord,
        payload: Mapping[str, Any],
        statistics: ImportStatistics,
    ) -> None:
        external_id = payload.get("id")
        if external_id is None:
            raise ImportDataError("Freshdesk conversation is missing id")
        digest = _payload_hash(payload)
        mapping = import_repository.get_mapping(
            db,
            market_id=market_id,
            provider="freshdesk",
            entity_type="conversation",
            external_id=external_id,
        )
        unchanged = bool(mapping and mapping.payload_hash == digest)
        record = db.get(TimelineEventRecord, mapping.internal_id) if mapping else None
        created = record is None
        private = bool(payload.get("private"))
        incoming = bool(payload.get("incoming"))
        event_type = "internal_note" if private else "inbound" if incoming else "public_reply"
        actor_id = payload.get("user_id") or payload.get("support_email") or "Freshdesk"
        created_at = _datetime(payload.get("created_at"))
        values = {
            "market_id": market_id,
            "ticket_id": ticket.id,
            "type": event_type,
            "channel": ticket.channel,
            "actor": str(actor_id),
            "body": _plain_text(payload.get("body_text") or payload.get("body")),
            "public": not private,
            "event_metadata": {
                "provider": "freshdesk",
                "external_conversation_id": str(external_id),
                "incoming": incoming,
                "private": private,
                "source": payload.get("source"),
                "attachments": payload.get("attachments") or [],
            },
            "created_at": created_at,
            "updated_at": _datetime(payload.get("updated_at"), fallback=created_at),
        }
        if record is None:
            record = TimelineEventRecord(
                id=_stable_id("timeline", "freshdesk", "conversation", external_id),
                **values,
            )
            db.add(record)
        elif mapping and mapping.payload_hash != digest:
            for key, value in values.items():
                setattr(record, key, value)
        db.flush()
        import_repository.set_mapping(
            db,
            market_id=market_id,
            provider="freshdesk",
            entity_type="conversation",
            external_id=external_id,
            internal_id=record.id,
            source_updated_at=_source_datetime(payload.get("updated_at")),
            payload_hash=digest,
            metadata={"ticket_id": ticket.id},
        )
        statistics.mark(
            "conversations",
            "created" if created else "unchanged" if unchanged else "updated",
        )

    def run_freshdesk_incremental(
        self,
        db: Session,
        *,
        client: FreshdeskClient,
        market_id: str,
        updated_since: str,
        dry_run: bool = False,
        batch_size: int = 100,
        started_by: str = "migration-cli",
    ) -> dict[str, Any]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        source_cursor = {"updated_since": updated_since}
        run = import_repository.begin_run(
            db,
            market_id=market_id,
            provider="freshdesk",
            mode="incremental",
            dry_run=dry_run,
            started_by=started_by,
            source_cursor=source_cursor,
        )
        db.commit()
        run_id = run.id
        statistics = ImportStatistics()
        latest_updated_at = updated_since
        original_suppression = db.info.get("omni_suppress_realtime_events")
        db.info["omni_suppress_realtime_events"] = True
        savepoint = db.begin_nested() if dry_run else None
        processed_since_commit = 0
        try:
            for contact in client.iter_contacts(updated_since=updated_since):
                self.upsert_freshdesk_contact(
                    db,
                    market_id=market_id,
                    payload=contact,
                    statistics=statistics,
                )
                processed_since_commit += 1
                candidate = str(contact.get("updated_at") or "")
                if candidate > latest_updated_at:
                    latest_updated_at = candidate
                if not dry_run and processed_since_commit >= batch_size:
                    checkpoint_run = db.get(ImportRunRecord, run_id)
                    if checkpoint_run is None:
                        raise ImportDataError("Import run disappeared during checkpoint")
                    checkpoint_run.statistics = statistics.payload()
                    import_repository.set_cursor(
                        db,
                        market_id=market_id,
                        provider="freshdesk",
                        resource="contacts",
                        cursor={"updated_since": latest_updated_at},
                    )
                    db.commit()
                    processed_since_commit = 0

            for source_ticket in client.iter_tickets(updated_since=updated_since):
                ticket = self.upsert_freshdesk_ticket(
                    db,
                    market_id=market_id,
                    payload=source_ticket,
                    client=client,
                    statistics=statistics,
                )
                for conversation in client.iter_ticket_conversations(source_ticket["id"]):
                    self.upsert_freshdesk_conversation(
                        db,
                        market_id=market_id,
                        ticket=ticket,
                        payload=conversation,
                        statistics=statistics,
                    )
                processed_since_commit += 1
                candidate = str(source_ticket.get("updated_at") or "")
                if candidate > latest_updated_at:
                    latest_updated_at = candidate
                if not dry_run and processed_since_commit >= batch_size:
                    checkpoint_run = db.get(ImportRunRecord, run_id)
                    if checkpoint_run is None:
                        raise ImportDataError("Import run disappeared during checkpoint")
                    checkpoint_run.statistics = statistics.payload()
                    import_repository.set_cursor(
                        db,
                        market_id=market_id,
                        provider="freshdesk",
                        resource="tickets",
                        cursor={"updated_since": latest_updated_at},
                    )
                    db.commit()
                    processed_since_commit = 0

            if savepoint is not None:
                savepoint.rollback()
            completed_run = db.get(ImportRunRecord, run_id)
            if completed_run is None:
                raise ImportDataError("Import run disappeared before completion")
            next_cursor = {"updated_since": latest_updated_at}
            if not dry_run:
                import_repository.set_cursor(
                    db,
                    market_id=market_id,
                    provider="freshdesk",
                    resource="tickets",
                    cursor=next_cursor,
                )
            import_repository.finish_run(
                completed_run,
                status="completed",
                statistics=statistics.payload(),
                next_cursor=next_cursor,
            )
            db.commit()
        except Exception as exc:
            if savepoint is not None and savepoint.is_active:
                savepoint.rollback()
            db.rollback()
            failed_run = db.get(ImportRunRecord, run_id)
            if failed_run is not None:
                import_repository.finish_run(
                    failed_run,
                    status="failed",
                    statistics=statistics.payload(),
                    next_cursor={"updated_since": latest_updated_at},
                    error_summary=str(exc),
                )
                db.commit()
            raise
        finally:
            if original_suppression is None:
                db.info.pop("omni_suppress_realtime_events", None)
            else:
                db.info["omni_suppress_realtime_events"] = original_suppression

        result = import_repository.read_run(db, market_id=market_id, run_id=run_id)
        if result is None:
            raise ImportDataError("Completed import run could not be read")
        if not dry_run:
            realtime_event_repository.record(
                db,
                market_id=market_id,
                event_type="import.completed",
                aggregate_type="import_run",
                aggregate_id=run_id,
                payload={"provider": "freshdesk", "statistics": statistics.payload()},
            )
        return result

    def upsert_freshchat_user(
        self,
        db: Session,
        *,
        market_id: str,
        payload: Mapping[str, Any],
        statistics: ImportStatistics,
    ) -> CustomerRecord:
        external_id = payload.get("id") or payload.get("user_id")
        if not external_id:
            raise ImportDataError("Freshchat user is missing id")
        digest = _payload_hash(payload)
        mapping = import_repository.get_mapping(
            db,
            market_id=market_id,
            provider="freshchat",
            entity_type="user",
            external_id=external_id,
        )
        if mapping and mapping.payload_hash == digest:
            existing = db.get(CustomerRecord, mapping.internal_id)
            if existing is not None:
                statistics.mark("users", "unchanged")
                return existing

        email = _normalized_email(payload.get("email"))
        phone = _normalized_phone(payload.get("phone") or payload.get("phone_no"))
        customer = db.get(CustomerRecord, mapping.internal_id) if mapping else None
        if customer is None and email:
            customer = db.scalar(
                select(CustomerRecord).where(
                    CustomerRecord.market_id == market_id,
                    CustomerRecord.email == email,
                )
            ) or self._identity_customer(
                db,
                market_id=market_id,
                identity_type="email",
                normalized_value=email,
            )
        if customer is None and phone:
            customer = self._identity_customer(
                db,
                market_id=market_id,
                identity_type="phone",
                normalized_value=phone,
            )
        created = customer is None
        first_name = str(payload.get("first_name") or "").strip()
        last_name = str(payload.get("last_name") or "").strip()
        name = " ".join(part for part in (first_name, last_name) if part)
        if not name:
            name = str(payload.get("name") or payload.get("reference_id") or "").strip()
        if not name:
            name = f"Freshchat user {str(external_id)[:24]}"
        created_at = _datetime(payload.get("created_time") or payload.get("created_at"))
        updated_at = _datetime(
            payload.get("updated_time") or payload.get("updated_at"),
            fallback=created_at,
        )
        if customer is None:
            customer = CustomerRecord(
                id=_stable_id("customer", "freshchat", "user", external_id),
                market_id=market_id,
                name=name,
                email=email or f"no-email+freshchat-{str(external_id)[:80]}@identity.omni.invalid",
                preferred_channels=["chat"],
                contact_points=[],
                tags=["freshchat-import"],
                notes="",
                created_at=created_at,
                updated_at=updated_at,
            )
            db.add(customer)
        else:
            customer.name = name or customer.name
            if email and customer.email.endswith("@identity.omni.invalid"):
                customer.email = email
            customer.preferred_channels = sorted(
                set(customer.preferred_channels or []) | {"chat"}
            )
            customer.tags = sorted(set(customer.tags or []) | {"freshchat-import"})
            customer.updated_at = updated_at

        points = list(customer.contact_points or [])
        for channel, value in (("email", email), ("voice", phone), ("chat", str(external_id))):
            if value and not any(
                point.get("channel") == channel and point.get("value") == value
                for point in points
            ):
                points.append({"channel": channel, "value": value, "verified": True})
        customer.contact_points = points
        if email:
            self._set_identity(
                db,
                market_id=market_id,
                customer_id=customer.id,
                provider="global",
                identity_type="email",
                value=email,
                verified=True,
                primary=True,
            )
        if phone:
            self._set_identity(
                db,
                market_id=market_id,
                customer_id=customer.id,
                provider="global",
                identity_type="phone",
                value=phone,
                verified=True,
            )
        self._set_identity(
            db,
            market_id=market_id,
            customer_id=customer.id,
            provider="freshchat",
            identity_type="external_id",
            value=external_id,
            verified=True,
            metadata={"reference_id": payload.get("reference_id")},
        )
        db.flush()
        import_repository.set_mapping(
            db,
            market_id=market_id,
            provider="freshchat",
            entity_type="user",
            external_id=external_id,
            internal_id=customer.id,
            source_updated_at=updated_at,
            payload_hash=digest,
        )
        statistics.mark("users", "created" if created else "updated")
        return customer

    def _freshchat_case(
        self,
        db: Session,
        *,
        market_id: str,
        customer_id: str,
        external_id: object,
        title: str,
        status: str,
        created_at: datetime,
        updated_at: datetime,
    ) -> CaseRecord:
        if status in _ACTIVE_TICKET_STATUSES:
            active = db.scalar(
                select(CaseRecord).where(
                    CaseRecord.market_id == market_id,
                    CaseRecord.customer_id == customer_id,
                    CaseRecord.status == "open",
                )
            )
            if active is not None:
                return active
            case_id = _stable_id("case", "freshchat", "active_customer", customer_id)
            previous = db.get(CaseRecord, case_id)
            if previous is not None:
                previous.status = "open"
                previous.title = title[:255]
                previous.updated_at = updated_at
                return previous
            case_status = "open"
        else:
            case_id = _stable_id("case", "freshchat", "conversation", external_id)
            previous = db.get(CaseRecord, case_id)
            if previous is not None:
                return previous
            case_status = "closed"
        record = CaseRecord(
            id=case_id,
            market_id=market_id,
            public_id=f"FCC-{str(external_id)[:28]}",
            customer_id=customer_id,
            title=title[:255],
            status=case_status,
            priority="normal",
            summary="",
            opened_by="Freshchat import",
            created_at=created_at,
            updated_at=updated_at,
        )
        db.add(record)
        db.flush()
        return record

    def upsert_freshchat_conversation(
        self,
        db: Session,
        *,
        market_id: str,
        customer: CustomerRecord,
        payload: Mapping[str, Any],
        statistics: ImportStatistics,
    ) -> ChatConversationRecord:
        external_id = payload.get("id") or payload.get("conversation_id")
        if not external_id:
            raise ImportDataError("Freshchat conversation is missing id")
        digest = _payload_hash(payload)
        mapping = import_repository.get_mapping(
            db,
            market_id=market_id,
            provider="freshchat",
            entity_type="conversation",
            external_id=external_id,
        )
        unchanged = bool(mapping and mapping.payload_hash == digest)
        conversation = db.get(ChatConversationRecord, mapping.internal_id) if mapping else None
        created = conversation is None
        source_status = str(payload.get("status") or "new").strip().lower()
        status = (
            "resolved"
            if source_status == "resolved"
            else "closed"
            if source_status == "closed"
            else "open"
        )
        created_at = _datetime(payload.get("created_time") or payload.get("created_at"))
        updated_at = _datetime(
            payload.get("updated_time") or payload.get("updated_at"),
            fallback=created_at,
        )
        properties = _decoded_json(payload.get("properties"))
        property_values: dict[str, Any] = {}
        if isinstance(properties, list):
            for item in properties:
                if isinstance(item, dict) and item.get("name"):
                    property_values[str(item["name"])] = item.get("value")
        elif isinstance(properties, dict):
            property_values = dict(properties)
        title = str(
            payload.get("subject")
            or property_values.get("subject")
            or property_values.get("title")
            or f"Freshchat conversation {str(external_id)[:18]}"
        ).strip()
        case = self._freshchat_case(
            db,
            market_id=market_id,
            customer_id=customer.id,
            external_id=external_id,
            title=title,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
        )
        assigned_agent_id = payload.get("assigned_agent_id") or payload.get(
            "assigned_org_agent_id"
        )
        assigned_group_id = payload.get("assigned_group_id")
        values = {
            "market_id": market_id,
            "public_id": f"FC-{str(external_id)[:32]}",
            "subject": title[:255],
            "customer_id": customer.id,
            "channel": "chat",
            "status": status,
            "priority": "normal",
            "topic_id": None,
            "assignee_id": None,
            "assigned_group_id": None,
            "source_account_id": str(payload.get("channel_id") or "") or None,
            "external_id": str(external_id),
            "last_message_at": updated_at,
            "resolved_at": updated_at if status in {"resolved", "closed"} else None,
            "reopened_at": None,
            "conversation_metadata": {
                **property_values,
                "freshchat": {
                    "conversation_id": str(external_id),
                    "channel_id": payload.get("channel_id"),
                    "assigned_agent_id": assigned_agent_id,
                    "assigned_group_id": assigned_group_id,
                    "status": source_status,
                },
            },
            "case_id": case.id,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        if conversation is None:
            conversation = ChatConversationRecord(
                id=_stable_id("conversation", "freshchat", "conversation", external_id),
                **values,
            )
            db.add(conversation)
        elif not unchanged:
            for key, value in values.items():
                setattr(conversation, key, value)
        db.flush()
        participant_id = _stable_id(
            "participant",
            "freshchat",
            "customer",
            f"{external_id}:{customer.id}",
        )
        participant = db.get(ChatParticipantRecord, participant_id)
        if participant is None:
            db.add(
                ChatParticipantRecord(
                    id=participant_id,
                    market_id=market_id,
                    conversation_id=conversation.id,
                    participant_type="customer",
                    customer_id=customer.id,
                    display_name=customer.name,
                    role="customer",
                    joined_at=created_at,
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )
        elif not unchanged:
            participant.display_name = customer.name
            participant.updated_at = updated_at
        import_repository.set_mapping(
            db,
            market_id=market_id,
            provider="freshchat",
            entity_type="conversation",
            external_id=external_id,
            internal_id=conversation.id,
            source_updated_at=updated_at,
            payload_hash=digest,
            metadata={"customer_id": customer.id},
        )
        statistics.mark(
            "chat_conversations",
            "created" if created else "unchanged" if unchanged else "updated",
        )
        return conversation

    def upsert_freshchat_message(
        self,
        db: Session,
        *,
        market_id: str,
        conversation: ChatConversationRecord,
        payload: Mapping[str, Any],
        statistics: ImportStatistics,
    ) -> ChatMessageRecord:
        external_id = payload.get("id") or payload.get("message_id")
        if not external_id:
            raise ImportDataError("Freshchat message is missing id")
        digest = _payload_hash(payload)
        mapping = import_repository.get_mapping(
            db,
            market_id=market_id,
            provider="freshchat",
            entity_type="message",
            external_id=external_id,
        )
        unchanged = bool(mapping and mapping.payload_hash == digest)
        record = db.get(ChatMessageRecord, mapping.internal_id) if mapping else None
        created = record is None
        actor = payload.get("actor")
        actor_type = ""
        actor_id: object = "Freshchat"
        if isinstance(actor, dict):
            actor_type = str(actor.get("actor_type") or actor.get("type") or "").lower()
            actor_id = actor.get("actor_id") or actor.get("id") or actor.get("name") or actor_id
        else:
            actor_type = str(payload.get("actor_type") or "").lower()
            actor_id = payload.get("actor_id") or payload.get("user_id") or actor_id
        message_type = str(payload.get("message_type") or "normal").lower()
        private = message_type in {"private", "private_note", "note"}
        incoming = actor_type in {"user", "customer", "end_user"}
        sender_type = (
            "customer"
            if incoming
            else "bot"
            if actor_type in {"bot", "system_bot"}
            else "system"
            if actor_type == "system"
            else "agent"
        )
        body, media_parts = _freshchat_message_body(payload)
        created_at = _datetime(payload.get("created_time") or payload.get("created_at"))
        updated_at = _datetime(
            payload.get("updated_time") or payload.get("updated_at"),
            fallback=created_at,
        )
        delivered_at = _source_datetime(
            payload.get("delivered_time") or payload.get("delivered_at")
        )
        read_at = _source_datetime(payload.get("read_time") or payload.get("read_at"))
        delivery_state = (
            "internal"
            if private
            else "read"
            if read_at
            else "delivered"
            if delivered_at or not incoming
            else "received"
        )
        values = {
            "market_id": market_id,
            "conversation_id": conversation.id,
            "sender_type": sender_type,
            "sender_id": conversation.customer_id if incoming else str(actor_id),
            "sender_name": str(actor_id),
            "visibility": "private" if private else "public",
            "body": body,
            "content": {"media_parts": media_parts} if media_parts else {},
            "delivery_state": delivery_state,
            "provider_message_id": str(external_id),
            "sent_at": created_at,
            "delivered_at": delivered_at,
            "read_at": read_at,
            "message_metadata": {
                "provider": "freshchat",
                "external_message_id": str(external_id),
                "actor_type": actor_type,
                "message_type": message_type,
            },
            "created_at": created_at,
            "updated_at": updated_at,
        }
        if record is None:
            record = ChatMessageRecord(
                id=_stable_id("message", "freshchat", "message", external_id),
                **values,
            )
            db.add(record)
        elif not unchanged:
            for key, value in values.items():
                setattr(record, key, value)
        if created_at > _datetime(conversation.last_message_at):
            conversation.last_message_at = created_at
        if incoming and body and conversation.subject.startswith("Freshchat conversation "):
            conversation.subject = body[:255]
        db.flush()
        import_repository.set_mapping(
            db,
            market_id=market_id,
            provider="freshchat",
            entity_type="message",
            external_id=external_id,
            internal_id=record.id,
            source_updated_at=_source_datetime(
                payload.get("updated_time") or payload.get("updated_at")
            ),
            payload_hash=digest,
            metadata={"conversation_id": conversation.id},
        )
        statistics.mark(
            "messages",
            "created" if created else "unchanged" if unchanged else "updated",
        )
        return record

    def run_freshchat_known_users(
        self,
        db: Session,
        *,
        client: FreshchatClient,
        market_id: str,
        user_ids: Iterable[str],
        from_time: str | None = None,
        dry_run: bool = False,
        batch_size: int = 25,
        started_by: str = "migration-cli",
    ) -> dict[str, Any]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        known_user_ids = list(dict.fromkeys(user_id.strip() for user_id in user_ids if user_id.strip()))
        if not known_user_ids:
            raise ValueError("At least one known Freshchat user ID is required")
        source_cursor = {"from_time": from_time, "known_user_count": len(known_user_ids)}
        run = import_repository.begin_run(
            db,
            market_id=market_id,
            provider="freshchat",
            mode="incremental",
            dry_run=dry_run,
            started_by=started_by,
            source_cursor=source_cursor,
        )
        db.commit()
        run_id = run.id
        statistics = ImportStatistics()
        latest_updated_at = from_time or ""
        original_suppression = db.info.get("omni_suppress_realtime_events")
        db.info["omni_suppress_realtime_events"] = True
        savepoint = db.begin_nested() if dry_run else None
        try:
            for index, user_id in enumerate(known_user_ids, start=1):
                source_user = client.get_user(user_id)
                source_user.setdefault("id", user_id)
                customer = self.upsert_freshchat_user(
                    db,
                    market_id=market_id,
                    payload=source_user,
                    statistics=statistics,
                )
                for conversation_id in client.list_user_conversations(user_id):
                    source_conversation = client.get_conversation(conversation_id)
                    source_conversation.setdefault("id", conversation_id)
                    conversation = self.upsert_freshchat_conversation(
                        db,
                        market_id=market_id,
                        customer=customer,
                        payload=source_conversation,
                        statistics=statistics,
                    )
                    for message in client.iter_messages(conversation_id, from_time=from_time):
                        self.upsert_freshchat_message(
                            db,
                            market_id=market_id,
                            conversation=conversation,
                            payload=message,
                            statistics=statistics,
                        )
                        candidate = str(
                            message.get("updated_time")
                            or message.get("created_time")
                            or message.get("updated_at")
                            or message.get("created_at")
                            or ""
                        )
                        if candidate > latest_updated_at:
                            latest_updated_at = candidate
                if not dry_run and index % batch_size == 0:
                    checkpoint_run = db.get(ImportRunRecord, run_id)
                    if checkpoint_run is None:
                        raise ImportDataError("Import run disappeared during checkpoint")
                    checkpoint_run.statistics = statistics.payload()
                    import_repository.set_cursor(
                        db,
                        market_id=market_id,
                        provider="freshchat",
                        resource="messages",
                        cursor={"from_time": latest_updated_at},
                    )
                    db.commit()

            if savepoint is not None:
                savepoint.rollback()
            completed_run = db.get(ImportRunRecord, run_id)
            if completed_run is None:
                raise ImportDataError("Import run disappeared before completion")
            next_cursor = {"from_time": latest_updated_at}
            if not dry_run:
                import_repository.set_cursor(
                    db,
                    market_id=market_id,
                    provider="freshchat",
                    resource="messages",
                    cursor=next_cursor,
                )
            import_repository.finish_run(
                completed_run,
                status="completed",
                statistics=statistics.payload(),
                next_cursor=next_cursor,
            )
            db.commit()
        except Exception as exc:
            if savepoint is not None and savepoint.is_active:
                savepoint.rollback()
            db.rollback()
            failed_run = db.get(ImportRunRecord, run_id)
            if failed_run is not None:
                import_repository.finish_run(
                    failed_run,
                    status="failed",
                    statistics=statistics.payload(),
                    next_cursor={"from_time": latest_updated_at},
                    error_summary=str(exc),
                )
                db.commit()
            raise
        finally:
            if original_suppression is None:
                db.info.pop("omni_suppress_realtime_events", None)
            else:
                db.info["omni_suppress_realtime_events"] = original_suppression

        result = import_repository.read_run(db, market_id=market_id, run_id=run_id)
        if result is None:
            raise ImportDataError("Completed import run could not be read")
        if not dry_run:
            realtime_event_repository.record(
                db,
                market_id=market_id,
                event_type="import.completed",
                aggregate_type="import_run",
                aggregate_id=run_id,
                payload={"provider": "freshchat", "statistics": statistics.payload()},
            )
        return result

    def _run_export(
        self,
        db: Session,
        *,
        provider: str,
        market_id: str,
        resources: list[
            tuple[
                str,
                Path,
                str | None,
                Callable[[Mapping[str, Any], ImportStatistics], None],
            ]
        ],
        dry_run: bool,
        batch_size: int,
        started_by: str,
    ) -> dict[str, Any]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        source_cursor = {name: path.name for name, path, _, _ in resources}
        run = import_repository.begin_run(
            db,
            market_id=market_id,
            provider=provider,
            mode="full_export",
            dry_run=dry_run,
            started_by=started_by,
            source_cursor=source_cursor,
        )
        db.commit()
        run_id = run.id
        statistics = ImportStatistics()
        checkpoints: dict[str, int] = {}
        original_suppression = db.info.get("omni_suppress_realtime_events")
        db.info["omni_suppress_realtime_events"] = True
        savepoint = db.begin_nested() if dry_run else None
        try:
            for resource_name, path, collection_key, processor in resources:
                count = 0
                for count, payload in enumerate(
                    iter_export_records(path, collection_key=collection_key),
                    start=1,
                ):
                    processor(payload, statistics)
                    checkpoints[resource_name] = count
                    if not dry_run and count % batch_size == 0:
                        checkpoint_run = db.get(ImportRunRecord, run_id)
                        if checkpoint_run is None:
                            raise ImportDataError("Import run disappeared during checkpoint")
                        checkpoint_run.statistics = statistics.payload()
                        import_repository.set_cursor(
                            db,
                            market_id=market_id,
                            provider=provider,
                            resource=resource_name,
                            cursor={"file": path.name, "records": count},
                        )
                        db.commit()
                checkpoints[resource_name] = count
                if not dry_run:
                    import_repository.set_cursor(
                        db,
                        market_id=market_id,
                        provider=provider,
                        resource=resource_name,
                        cursor={"file": path.name, "records": count, "complete": True},
                    )
                    db.commit()

            if savepoint is not None:
                savepoint.rollback()
            completed_run = db.get(ImportRunRecord, run_id)
            if completed_run is None:
                raise ImportDataError("Import run disappeared before completion")
            next_cursor = {"files": checkpoints}
            import_repository.finish_run(
                completed_run,
                status="completed",
                statistics=statistics.payload(),
                next_cursor=next_cursor,
            )
            db.commit()
        except Exception as exc:
            if savepoint is not None and savepoint.is_active:
                savepoint.rollback()
            db.rollback()
            failed_run = db.get(ImportRunRecord, run_id)
            if failed_run is not None:
                import_repository.finish_run(
                    failed_run,
                    status="failed",
                    statistics=statistics.payload(),
                    next_cursor={"files": checkpoints},
                    error_summary=str(exc),
                )
                db.commit()
            raise
        finally:
            if original_suppression is None:
                db.info.pop("omni_suppress_realtime_events", None)
            else:
                db.info["omni_suppress_realtime_events"] = original_suppression

        result = import_repository.read_run(db, market_id=market_id, run_id=run_id)
        if result is None:
            raise ImportDataError("Completed import run could not be read")
        if not dry_run:
            realtime_event_repository.record(
                db,
                market_id=market_id,
                event_type="import.completed",
                aggregate_type="import_run",
                aggregate_id=run_id,
                payload={"provider": provider, "statistics": statistics.payload()},
            )
        return result

    def run_freshdesk_export(
        self,
        db: Session,
        *,
        market_id: str,
        contacts_path: Path,
        tickets_path: Path,
        conversations_path: Path,
        dry_run: bool = False,
        batch_size: int = 500,
        started_by: str = "migration-cli",
    ) -> dict[str, Any]:
        def contact_processor(payload: Mapping[str, Any], stats: ImportStatistics) -> None:
            self.upsert_freshdesk_contact(
                db,
                market_id=market_id,
                payload=payload,
                statistics=stats,
            )

        def ticket_processor(payload: Mapping[str, Any], stats: ImportStatistics) -> None:
            self.upsert_freshdesk_ticket(
                db,
                market_id=market_id,
                payload=payload,
                client=None,
                statistics=stats,
            )

        def conversation_processor(payload: Mapping[str, Any], stats: ImportStatistics) -> None:
            external_ticket_id = payload.get("ticket_id") or payload.get("freshdesk_ticket_id")
            if external_ticket_id is None:
                raise ImportDataError("Freshdesk conversation export row is missing ticket_id")
            ticket_mapping = import_repository.get_mapping(
                db,
                market_id=market_id,
                provider="freshdesk",
                entity_type="ticket",
                external_id=external_ticket_id,
            )
            ticket = db.get(TicketRecord, ticket_mapping.internal_id) if ticket_mapping else None
            if ticket is None:
                raise ImportDataError(
                    f"Freshdesk conversation references unknown ticket {external_ticket_id}"
                )
            self.upsert_freshdesk_conversation(
                db,
                market_id=market_id,
                ticket=ticket,
                payload=payload,
                statistics=stats,
            )

        return self._run_export(
            db,
            provider="freshdesk",
            market_id=market_id,
            resources=[
                ("contacts", contacts_path, "contacts", contact_processor),
                ("tickets", tickets_path, "tickets", ticket_processor),
                ("conversations", conversations_path, "conversations", conversation_processor),
            ],
            dry_run=dry_run,
            batch_size=batch_size,
            started_by=started_by,
        )

    def _freshchat_user_id_from_conversation(self, payload: Mapping[str, Any]) -> str:
        direct = payload.get("user_id") or payload.get("freshchat_user_id")
        if direct:
            return str(direct)
        user = _decoded_json(payload.get("user"))
        if isinstance(user, dict) and (user.get("id") or user.get("user_id")):
            return str(user.get("id") or user.get("user_id"))
        for key in ("users", "participants", "actors"):
            entries = _list_value(payload.get(key))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                actor_type = str(
                    entry.get("actor_type") or entry.get("user_type") or entry.get("type") or ""
                ).lower()
                if actor_type in {"user", "customer", "end_user"}:
                    value = entry.get("id") or entry.get("user_id") or entry.get("actor_id")
                    if value:
                        return str(value)
        raise ImportDataError(
            f"Freshchat conversation {payload.get('id')} does not identify its customer user"
        )

    def run_freshchat_export(
        self,
        db: Session,
        *,
        market_id: str,
        users_path: Path,
        conversations_path: Path,
        messages_path: Path,
        dry_run: bool = False,
        batch_size: int = 500,
        started_by: str = "migration-cli",
    ) -> dict[str, Any]:
        def user_processor(payload: Mapping[str, Any], stats: ImportStatistics) -> None:
            self.upsert_freshchat_user(
                db,
                market_id=market_id,
                payload=payload,
                statistics=stats,
            )

        def conversation_processor(payload: Mapping[str, Any], stats: ImportStatistics) -> None:
            user_id = self._freshchat_user_id_from_conversation(payload)
            user_mapping = import_repository.get_mapping(
                db,
                market_id=market_id,
                provider="freshchat",
                entity_type="user",
                external_id=user_id,
            )
            customer = db.get(CustomerRecord, user_mapping.internal_id) if user_mapping else None
            if customer is None:
                raise ImportDataError(
                    f"Freshchat conversation references unknown user {user_id}"
                )
            self.upsert_freshchat_conversation(
                db,
                market_id=market_id,
                customer=customer,
                payload=payload,
                statistics=stats,
            )

        def message_processor(payload: Mapping[str, Any], stats: ImportStatistics) -> None:
            conversation_id = payload.get("conversation_id") or payload.get(
                "freshchat_conversation_id"
            )
            if not conversation_id:
                raise ImportDataError("Freshchat message export row is missing conversation_id")
            conversation_mapping = import_repository.get_mapping(
                db,
                market_id=market_id,
                provider="freshchat",
                entity_type="conversation",
                external_id=conversation_id,
            )
            conversation = (
                db.get(ChatConversationRecord, conversation_mapping.internal_id)
                if conversation_mapping
                else None
            )
            if conversation is None:
                raise ImportDataError(
                    f"Freshchat message references unknown conversation {conversation_id}"
                )
            self.upsert_freshchat_message(
                db,
                market_id=market_id,
                conversation=conversation,
                payload=payload,
                statistics=stats,
            )

        return self._run_export(
            db,
            provider="freshchat",
            market_id=market_id,
            resources=[
                ("users", users_path, "users", user_processor),
                ("conversations", conversations_path, "conversations", conversation_processor),
                ("messages", messages_path, "messages", message_processor),
            ],
            dry_run=dry_run,
            batch_size=batch_size,
            started_by=started_by,
        )


freshworks_import_service = FreshworksImportService()
