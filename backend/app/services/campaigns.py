from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import re
from typing import cast
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.db.audit import write_audit_event
from app.db.integration_credentials import integration_credential_settings_repository
from app.db.models import (
    CampaignConsentRecord,
    CampaignDeliveryRecord,
    CampaignRecord,
    ConnectorAccountRecord,
    ConnectorEventRecord,
    CustomerIdentityRecord,
    CustomerRecord,
)
from app.models.campaigns import (
    CampaignAudience,
    CampaignChannel,
    CampaignConsentResponse,
    CampaignConsentStatus,
    CampaignDeliveryResponse,
    CampaignDeliveryStatus,
    CampaignDeliverySummary,
    CampaignLaunchResponse,
    CampaignProviderReadiness,
    CampaignResponse,
    CampaignStatus,
    CreateCampaignRequest,
    SetCampaignConsentRequest,
    UpdateCampaignRequest,
)
from app.models.domain import ChannelType, ConnectorDirection, utc_now
from app.services.campaign_delivery import (
    CampaignDeliveryTransport,
    CampaignSendRequest,
    campaign_delivery_transport,
)

_IDENTITY_TYPES: dict[CampaignChannel, set[str]] = {
    "whatsapp": {"phone", "whatsapp"},
    "sms": {"phone", "sms"},
    "facebook": {"facebook", "facebook_psid"},
    "instagram": {"instagram", "instagram_scoped_id"},
}
_DUE_STATUSES = {"queued", "failed"}
_FINAL_STATUSES = {"sent", "delivered", "read", "dead_lettered", "suppressed"}


@dataclass
class CampaignDispatchResult:
    processed_ids: list[str] = field(default_factory=list)
    sent_ids: list[str] = field(default_factory=list)
    retrying_ids: list[str] = field(default_factory=list)
    dead_lettered_ids: list[str] = field(default_factory=list)
    suppressed_ids: list[str] = field(default_factory=list)


def _provider_readiness(
    db: Session,
    *,
    market_id: str,
    channel: CampaignChannel,
) -> CampaignProviderReadiness:
    account = db.scalar(
        select(ConnectorAccountRecord).where(
            ConnectorAccountRecord.market_id == market_id,
            ConnectorAccountRecord.provider == channel,
        )
    )
    if account is None:
        return CampaignProviderReadiness(
            channel=channel,
            configured=False,
            detail="No connector account is configured for this market.",
        )
    if not account.outbound_enabled:
        return CampaignProviderReadiness(
            channel=channel,
            configured=False,
            detail="Outbound delivery is disabled for this connector account.",
        )
    if account.status != "connected" or not account.secret_configured:
        return CampaignProviderReadiness(
            channel=channel,
            configured=False,
            detail="Provider credentials are not connected.",
        )
    credentials = integration_credential_settings_repository.runtime_credentials(
        db,
        market_id=market_id,
    )
    missing = campaign_delivery_transport.missing_settings(channel, credentials)
    if missing:
        return CampaignProviderReadiness(
            channel=channel,
            configured=False,
            detail=f"Missing provider settings: {', '.join(missing)}.",
        )
    return CampaignProviderReadiness(
        channel=channel,
        configured=True,
        detail="Provider account is connected for proactive delivery.",
    )


def _matches_audience(customer: CustomerRecord, audience: CampaignAudience) -> bool:
    if audience.include_all:
        return True
    customer_tags = {str(tag).strip().lower() for tag in customer.tags or []}
    return bool(customer_tags.intersection(audience.tags_any))


def _normalize_recipient(channel: CampaignChannel, value: str) -> str:
    recipient = value.strip()
    prefixes = {
        "whatsapp": ("whatsapp:", "tel:", "phone:"),
        "sms": ("sms:", "tel:", "phone:"),
        "facebook": ("fb:", "facebook:", "messenger:", "psid:"),
        "instagram": ("ig:", "instagram:", "igsid:", "instagram_scoped_id:"),
    }
    for prefix in prefixes[channel]:
        if recipient.lower().startswith(prefix):
            recipient = recipient.split(":", 1)[1]
            break
    if channel in {"whatsapp", "sms"}:
        return re.sub(r"[\s().-]+", "", recipient)
    if channel == "instagram" and recipient.startswith("@"):
        return ""
    return recipient.strip()


def _recipient_for_customer(
    db: Session,
    *,
    market_id: str,
    customer: CustomerRecord,
    channel: CampaignChannel,
) -> str | None:
    identities = db.scalars(
        select(CustomerIdentityRecord)
        .where(
            CustomerIdentityRecord.market_id == market_id,
            CustomerIdentityRecord.customer_id == customer.id,
            CustomerIdentityRecord.identity_type.in_(_IDENTITY_TYPES[channel]),
            CustomerIdentityRecord.verified.is_(True),
        )
        .order_by(CustomerIdentityRecord.primary.desc(), CustomerIdentityRecord.created_at.asc())
    ).all()
    for identity in identities:
        recipient = _normalize_recipient(channel, identity.normalized_value)
        if recipient:
            return recipient
    allowed_points = _IDENTITY_TYPES[channel] | {channel}
    for point in customer.contact_points or []:
        point_channel = str(point.get("channel") or point.get("type") or "").strip().lower()
        if point_channel not in allowed_points or point.get("verified") is False:
            continue
        recipient = _normalize_recipient(channel, str(point.get("value") or ""))
        if recipient:
            return recipient
    return None


def _audience_customers(
    db: Session,
    *,
    market_id: str,
    audience: CampaignAudience,
) -> list[CustomerRecord]:
    return [
        customer
        for customer in db.scalars(
            select(CustomerRecord)
            .where(CustomerRecord.market_id == market_id)
            .order_by(CustomerRecord.id.asc())
        ).all()
        if _matches_audience(customer, audience)
    ]


def _estimated_recipients(
    db: Session,
    *,
    market_id: str,
    channel: CampaignChannel,
    audience: CampaignAudience,
) -> int:
    return sum(
        1
        for customer in _audience_customers(db, market_id=market_id, audience=audience)
        if _recipient_for_customer(
            db,
            market_id=market_id,
            customer=customer,
            channel=channel,
        )
    )


def _consented_recipients(
    db: Session,
    *,
    market_id: str,
    channel: CampaignChannel,
    audience: CampaignAudience,
) -> int:
    count = 0
    for customer in _audience_customers(db, market_id=market_id, audience=audience):
        consent = db.scalar(
            select(CampaignConsentRecord).where(
                CampaignConsentRecord.market_id == market_id,
                CampaignConsentRecord.customer_id == customer.id,
                CampaignConsentRecord.channel == channel,
                CampaignConsentRecord.status == "opted_in",
            )
        )
        if consent is not None and _recipient_for_customer(
            db,
            market_id=market_id,
            customer=customer,
            channel=channel,
        ):
            count += 1
    return count


def _delivery_summary(db: Session, campaign_id: str) -> CampaignDeliverySummary:
    counts = {
        row[0]: row[1]
        for row in db.execute(
            select(CampaignDeliveryRecord.status, func.count(CampaignDeliveryRecord.id))
            .where(CampaignDeliveryRecord.campaign_id == campaign_id)
            .group_by(CampaignDeliveryRecord.status)
        ).all()
    }
    return CampaignDeliverySummary(
        total=sum(counts.values()),
        **{
            field: int(counts.get(field, 0))
            for field in CampaignDeliverySummary.model_fields
            if field != "total"
        },
    )


def _response(db: Session, record: CampaignRecord) -> CampaignResponse:
    campaign_channel = cast(CampaignChannel, record.channel)
    audience = CampaignAudience.model_validate(record.audience)
    return CampaignResponse(
        id=record.id,
        market_id=record.market_id,
        name=record.name,
        channel=campaign_channel,
        status=cast(CampaignStatus, record.status),
        message_body=record.message_body,
        audience=audience,
        scheduled_at=record.scheduled_at,
        template_name=record.template_name,
        template_language=record.template_language,
        template_variables=list(record.template_variables or []),
        created_by=record.created_by,
        estimated_recipients=_estimated_recipients(
            db,
            market_id=record.market_id,
            channel=campaign_channel,
            audience=audience,
        ),
        consented_recipients=_consented_recipients(
            db,
            market_id=record.market_id,
            channel=campaign_channel,
            audience=audience,
        ),
        provider=_provider_readiness(
            db,
            market_id=record.market_id,
            channel=campaign_channel,
        ),
        delivery_summary=_delivery_summary(db, record.id),
        launched_at=record.launched_at,
        completed_at=record.completed_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _consent_response(db: Session, record: CampaignConsentRecord) -> CampaignConsentResponse:
    customer = db.get(CustomerRecord, record.customer_id)
    return CampaignConsentResponse(
        id=record.id,
        market_id=record.market_id,
        customer_id=record.customer_id,
        customer_name=customer.name if customer is not None else record.customer_id,
        customer_email=customer.email if customer is not None else "",
        channel=cast(CampaignChannel, record.channel),
        status=cast(CampaignConsentStatus, record.status),
        source=record.source,
        evidence=record.evidence,
        captured_by=record.captured_by,
        captured_at=record.captured_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _delivery_response(record: CampaignDeliveryRecord) -> CampaignDeliveryResponse:
    return CampaignDeliveryResponse(
        id=record.id,
        campaign_id=record.campaign_id,
        market_id=record.market_id,
        customer_id=record.customer_id,
        channel=cast(CampaignChannel, record.channel),
        recipient=record.recipient,
        status=cast(CampaignDeliveryStatus, record.status),
        idempotency_key=record.idempotency_key,
        consent_id=record.consent_id,
        attempts=record.attempts,
        max_attempts=record.max_attempts,
        next_attempt_at=record.next_attempt_at,
        sent_at=record.sent_at,
        delivered_at=record.delivered_at,
        read_at=record.read_at,
        external_id=record.external_id,
        last_error=record.last_error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class CampaignService:
    def list_campaigns(self, db: Session, *, market_id: str) -> list[CampaignResponse]:
        records = db.scalars(
            select(CampaignRecord)
            .where(CampaignRecord.market_id == market_id)
            .order_by(CampaignRecord.updated_at.desc())
        ).all()
        return [_response(db, record) for record in records]

    def readiness(self, db: Session, *, market_id: str) -> list[CampaignProviderReadiness]:
        return [
            _provider_readiness(db, market_id=market_id, channel=channel)
            for channel in _IDENTITY_TYPES
        ]

    def create(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        request: CreateCampaignRequest,
    ) -> CampaignResponse:
        record = CampaignRecord(
            id=f"campaign_{uuid4().hex}",
            market_id=market_id,
            name=request.name.strip(),
            channel=request.channel,
            status="draft",
            message_body=request.message_body.strip(),
            audience=request.audience.model_dump(),
            scheduled_at=request.scheduled_at,
            template_name=request.template_name.strip(),
            template_language=request.template_language.strip(),
            template_variables=[value.strip() for value in request.template_variables],
            created_by=actor,
        )
        db.add(record)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="A campaign with this name already exists in the active market",
            ) from exc
        write_audit_event(
            db,
            actor=actor,
            action="campaign.create",
            entity_type="campaign",
            entity_id=record.id,
            market_id=market_id,
            details={"channel": record.channel, "status": record.status},
        )
        db.commit()
        db.refresh(record)
        return _response(db, record)

    def update(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        campaign_id: str,
        request: UpdateCampaignRequest,
    ) -> CampaignResponse:
        record = db.get(CampaignRecord, campaign_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        patch = request.model_dump(exclude_unset=True)
        delivery_count = db.scalar(
            select(func.count(CampaignDeliveryRecord.id)).where(
                CampaignDeliveryRecord.campaign_id == record.id
            )
        ) or 0
        content_fields = {
            "name",
            "message_body",
            "audience",
            "scheduled_at",
            "template_name",
            "template_language",
            "template_variables",
        }
        if delivery_count and content_fields.intersection(patch):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Launched campaign content and audience cannot be changed",
            )
        requested_status = patch.pop("status", None)
        if requested_status is not None:
            if requested_status == "paused" and record.status not in {"completed", "cancelled"}:
                record.status = "paused"
            elif requested_status == "draft" and record.status == "paused" and not delivery_count:
                record.status = "draft"
            elif requested_status == "running" and record.status == "paused" and delivery_count:
                record.status = "running"
            elif requested_status == "cancelled" and record.status != "completed":
                record.status = "cancelled"
            else:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=f"Campaign cannot move from {record.status} to {requested_status}",
                )
        if "audience" in patch and patch["audience"] is not None:
            patch["audience"] = request.audience.model_dump() if request.audience else record.audience
        for key, value in patch.items():
            if key in {"name", "message_body", "template_name", "template_language"} and isinstance(
                value, str
            ):
                value = value.strip()
            if key == "template_variables" and value is not None:
                value = [str(item).strip() for item in value]
            setattr(record, key, value)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="A campaign with this name already exists in the active market",
            ) from exc
        changed_fields = sorted(set(patch) | ({"status"} if requested_status else set()))
        write_audit_event(
            db,
            actor=actor,
            action="campaign.update",
            entity_type="campaign",
            entity_id=record.id,
            market_id=market_id,
            details={"changed_fields": changed_fields, "status": record.status},
        )
        db.commit()
        db.refresh(record)
        return _response(db, record)

    def set_consent(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        request: SetCampaignConsentRequest,
    ) -> CampaignConsentResponse:
        customer = db.get(CustomerRecord, request.customer_id)
        if customer is None or customer.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Customer not found")
        record = db.scalar(
            select(CampaignConsentRecord).where(
                CampaignConsentRecord.market_id == market_id,
                CampaignConsentRecord.customer_id == request.customer_id,
                CampaignConsentRecord.channel == request.channel,
            )
        )
        previous_status = record.status if record else None
        if record is None:
            record = CampaignConsentRecord(
                id=f"campaign_consent_{uuid4().hex}",
                market_id=market_id,
                customer_id=request.customer_id,
                channel=request.channel,
                status=request.status,
                source=request.source.strip(),
                evidence=request.evidence.strip(),
                captured_by=actor,
                captured_at=utc_now(),
            )
            db.add(record)
        else:
            record.status = request.status
            record.source = request.source.strip()
            record.evidence = request.evidence.strip()
            record.captured_by = actor
            record.captured_at = utc_now()
        db.flush()
        write_audit_event(
            db,
            actor=actor,
            action="campaign.consent.update",
            entity_type="customer",
            entity_id=customer.id,
            market_id=market_id,
            details={
                "channel": request.channel,
                "previous_status": previous_status,
                "status": request.status,
                "source": request.source,
                "consent_id": record.id,
            },
        )
        db.commit()
        db.refresh(record)
        return _consent_response(db, record)

    def list_consents(
        self,
        db: Session,
        *,
        market_id: str,
        customer_id: str | None = None,
    ) -> list[CampaignConsentResponse]:
        query = select(CampaignConsentRecord).where(CampaignConsentRecord.market_id == market_id)
        if customer_id:
            query = query.where(CampaignConsentRecord.customer_id == customer_id)
        records = db.scalars(query.order_by(CampaignConsentRecord.updated_at.desc())).all()
        return [_consent_response(db, record) for record in records]

    def launch(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        campaign_id: str,
    ) -> CampaignLaunchResponse:
        record = db.get(CampaignRecord, campaign_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        if record.status in {"completed", "cancelled"}:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Campaign is already final")
        channel = cast(CampaignChannel, record.channel)
        readiness = _provider_readiness(db, market_id=market_id, channel=channel)
        if not readiness.configured:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=readiness.detail)
        if channel == "whatsapp" and not record.template_name.strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="WhatsApp proactive campaigns require an approved template name",
            )
        existing = db.scalar(
            select(func.count(CampaignDeliveryRecord.id)).where(
                CampaignDeliveryRecord.campaign_id == record.id
            )
        ) or 0
        if existing:
            return CampaignLaunchResponse(
                campaign=_response(db, record),
                created_deliveries=0,
                existing_deliveries=existing,
            )
        audience = CampaignAudience.model_validate(record.audience)
        deliveries: list[CampaignDeliveryRecord] = []
        scheduled_at = record.scheduled_at or utc_now()
        for customer in _audience_customers(db, market_id=market_id, audience=audience):
            consent = db.scalar(
                select(CampaignConsentRecord).where(
                    CampaignConsentRecord.market_id == market_id,
                    CampaignConsentRecord.customer_id == customer.id,
                    CampaignConsentRecord.channel == channel,
                    CampaignConsentRecord.status == "opted_in",
                )
            )
            if consent is None:
                continue
            recipient = _recipient_for_customer(
                db,
                market_id=market_id,
                customer=customer,
                channel=channel,
            )
            if not recipient:
                continue
            delivery = CampaignDeliveryRecord(
                id=f"campaign_delivery_{uuid4().hex}",
                campaign_id=record.id,
                market_id=market_id,
                customer_id=customer.id,
                consent_id=consent.id,
                channel=channel,
                recipient=recipient,
                status="queued",
                idempotency_key=f"campaign:{record.id}:customer:{customer.id}",
                attempts=0,
                max_attempts=5,
                next_attempt_at=scheduled_at,
                provider_payload={},
            )
            db.add(delivery)
            deliveries.append(delivery)
        if not deliveries:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No consented, verified recipients match this campaign audience",
            )
        now = utc_now()
        record.status = "scheduled" if scheduled_at > now else "running"
        record.launched_at = now
        record.completed_at = None
        db.flush()
        write_audit_event(
            db,
            actor=actor,
            action="campaign.launch",
            entity_type="campaign",
            entity_id=record.id,
            market_id=market_id,
            details={
                "channel": channel,
                "deliveries": len(deliveries),
                "scheduled_at": scheduled_at.isoformat(),
            },
        )
        db.commit()
        db.refresh(record)
        return CampaignLaunchResponse(
            campaign=_response(db, record),
            created_deliveries=len(deliveries),
            existing_deliveries=0,
        )

    def list_deliveries(
        self,
        db: Session,
        *,
        market_id: str,
        campaign_id: str,
    ) -> list[CampaignDeliveryResponse]:
        campaign = db.get(CampaignRecord, campaign_id)
        if campaign is None or campaign.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        records = db.scalars(
            select(CampaignDeliveryRecord)
            .where(
                CampaignDeliveryRecord.market_id == market_id,
                CampaignDeliveryRecord.campaign_id == campaign_id,
            )
            .order_by(CampaignDeliveryRecord.created_at.asc())
        ).all()
        return [_delivery_response(record) for record in records]

    def dispatch_due(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        limit: int = 100,
        transport: CampaignDeliveryTransport = campaign_delivery_transport,
    ) -> CampaignDispatchResult:
        now = utc_now()
        records = list(
            db.scalars(
                select(CampaignDeliveryRecord)
                .where(
                    CampaignDeliveryRecord.market_id == market_id,
                    CampaignDeliveryRecord.status.in_(_DUE_STATUSES),
                    or_(
                        CampaignDeliveryRecord.next_attempt_at.is_(None),
                        CampaignDeliveryRecord.next_attempt_at <= now,
                    ),
                )
                .order_by(CampaignDeliveryRecord.created_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        result = CampaignDispatchResult()
        credentials = integration_credential_settings_repository.runtime_credentials(
            db,
            market_id=market_id,
        )
        touched_campaign_ids: set[str] = set()
        for delivery in records:
            campaign = db.get(CampaignRecord, delivery.campaign_id)
            if campaign is None or campaign.status in {"paused", "cancelled", "completed"}:
                continue
            touched_campaign_ids.add(campaign.id)
            if campaign.status == "scheduled":
                campaign.status = "running"
            consent = db.get(CampaignConsentRecord, delivery.consent_id)
            if consent is None or consent.status != "opted_in":
                delivery.status = "suppressed"
                delivery.last_error = "Customer consent was withdrawn before delivery."
                delivery.next_attempt_at = None
                result.processed_ids.append(delivery.id)
                result.suppressed_ids.append(delivery.id)
                write_audit_event(
                    db,
                    actor=actor,
                    action="campaign.delivery.suppressed",
                    entity_type="campaign_delivery",
                    entity_id=delivery.id,
                    market_id=market_id,
                    details={"campaign_id": campaign.id, "customer_id": delivery.customer_id},
                )
                continue
            delivery.status = "sending"
            delivery.attempts += 1
            db.flush()
            send_result = transport.send(
                CampaignSendRequest(
                    delivery_id=delivery.id,
                    campaign_id=campaign.id,
                    market_id=market_id,
                    customer_id=delivery.customer_id,
                    channel=cast(CampaignChannel, delivery.channel),
                    recipient=delivery.recipient,
                    body=campaign.message_body,
                    idempotency_key=delivery.idempotency_key,
                    template_name=campaign.template_name,
                    template_language=campaign.template_language,
                    template_variables=list(campaign.template_variables or []),
                ),
                credentials,
            )
            result.processed_ids.append(delivery.id)
            delivery.provider_payload = {
                **(delivery.provider_payload or {}),
                "adapter": send_result.adapter,
                "send": send_result.payload,
            }
            if send_result.succeeded:
                delivery.status = "sent"
                delivery.external_id = send_result.external_id
                delivery.sent_at = now
                delivery.last_error = None
                delivery.next_attempt_at = None
                result.sent_ids.append(delivery.id)
                action = "campaign.delivery.sent"
            else:
                delivery.last_error = send_result.error or "Provider delivery failed."
                if delivery.attempts >= delivery.max_attempts:
                    delivery.status = "dead_lettered"
                    delivery.next_attempt_at = None
                    result.dead_lettered_ids.append(delivery.id)
                    action = "campaign.delivery.dead_lettered"
                else:
                    delivery.status = "failed"
                    delivery.next_attempt_at = now + timedelta(
                        minutes=min(2 ** max(delivery.attempts - 1, 0), 60)
                    )
                    result.retrying_ids.append(delivery.id)
                    action = "campaign.delivery.retry_scheduled"
            write_audit_event(
                db,
                actor=actor,
                action=action,
                entity_type="campaign_delivery",
                entity_id=delivery.id,
                market_id=market_id,
                details={
                    "campaign_id": campaign.id,
                    "customer_id": delivery.customer_id,
                    "attempts": delivery.attempts,
                    "status": delivery.status,
                    "external_id": delivery.external_id,
                    "error": delivery.last_error,
                },
            )
        db.flush()
        for campaign_id in touched_campaign_ids:
            campaign = db.get(CampaignRecord, campaign_id)
            if campaign is None or campaign.status in {"paused", "cancelled"}:
                continue
            remaining = db.scalar(
                select(func.count(CampaignDeliveryRecord.id)).where(
                    CampaignDeliveryRecord.campaign_id == campaign_id,
                    CampaignDeliveryRecord.status.not_in(_FINAL_STATUSES),
                )
            ) or 0
            if remaining == 0:
                campaign.status = "completed"
                campaign.completed_at = utc_now()
        db.commit()
        return result

    def record_delivery_receipt(
        self,
        db: Session,
        *,
        market_id: str,
        provider: ChannelType,
        status_label: str,
        provider_message_id: str | None,
        campaign_delivery_id: str | None,
        idempotency_key: str | None,
        delivery_id: str | None,
        raw_payload: dict,
        actor: str = "provider-webhook",
    ) -> CampaignDeliveryResponse | None:
        if not provider_message_id and not campaign_delivery_id and not idempotency_key:
            return None
        receipt_matches: list[ColumnElement[bool]] = []
        if campaign_delivery_id:
            receipt_matches.append(CampaignDeliveryRecord.id == campaign_delivery_id)
        if provider_message_id:
            receipt_matches.append(CampaignDeliveryRecord.external_id == provider_message_id)
        if idempotency_key:
            receipt_matches.append(CampaignDeliveryRecord.idempotency_key == idempotency_key)
        delivery = db.scalar(
            select(CampaignDeliveryRecord).where(
                CampaignDeliveryRecord.market_id == market_id,
                CampaignDeliveryRecord.channel == provider.value,
                or_(*receipt_matches),
            )
        )
        if delivery is None:
            return None
        normalized = status_label.strip().lower() or "unknown"
        now = utc_now()
        if normalized in {"read", "seen"}:
            delivery.status = "read"
            delivery.read_at = now
            delivery.delivered_at = delivery.delivered_at or now
        elif normalized in {"delivered", "delivery"}:
            delivery.status = "delivered"
            delivery.delivered_at = now
        elif normalized in {"sent", "accepted", "queued", "success", "ok"}:
            delivery.status = "sent"
            delivery.sent_at = delivery.sent_at or now
        elif normalized in {"failed", "undelivered", "rejected", "error", "blocked", "expired"}:
            delivery.status = "dead_lettered"
            delivery.last_error = f"Provider delivery receipt reported {status_label}."
        receipt_payload = {
            "status": status_label,
            "normalized_status": normalized,
            "provider_message_id": provider_message_id,
            "delivery_id": delivery_id,
            "received_at": now.isoformat(),
            "payload": raw_payload,
        }
        delivery.provider_payload = {
            **(delivery.provider_payload or {}),
            "delivery_receipt": receipt_payload,
        }
        receipt_external_id = (
            f"receipt:{delivery_id}"
            if delivery_id
            else f"receipt:{provider_message_id or delivery.id}:{normalized}"
        )
        db.add(
            ConnectorEventRecord(
                id=f"connector_{uuid4().hex}",
                market_id=market_id,
                provider=provider.value,
                direction=ConnectorDirection.inbound.value,
                external_id=receipt_external_id,
                ticket_id=None,
                status="campaign-delivery-receipt",
                payload={
                    "campaign_delivery_id": delivery.id,
                    "campaign_id": delivery.campaign_id,
                    "provider_message_id": provider_message_id,
                    "receipt_status": status_label,
                    "metadata": {
                        "webhook_delivery_id": delivery_id,
                        "source": "provider_campaign_delivery_receipt",
                    },
                    "payload": raw_payload,
                },
            )
        )
        write_audit_event(
            db,
            actor=actor,
            action="campaign.delivery.receipt",
            entity_type="campaign_delivery",
            entity_id=delivery.id,
            market_id=market_id,
            details={
                "campaign_id": delivery.campaign_id,
                "provider": provider.value,
                "status": status_label,
                "normalized_status": normalized,
                "provider_message_id": provider_message_id,
                "delivery_id": delivery_id,
            },
        )
        db.flush()
        return _delivery_response(delivery)


campaign_service = CampaignService()
