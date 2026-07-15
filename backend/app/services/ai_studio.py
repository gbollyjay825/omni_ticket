from typing import cast
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.audit import write_audit_event
from app.db.integration_credentials import integration_credential_settings_repository
from app.db.models import AiAgentRecord, AiDecisionRecord, TicketRecord
from app.db.settings import get_or_create_workspace_settings
from app.models.ai_studio import (
    AiAgentResponse,
    AiAgentStatus,
    AiDecisionResponse,
    AiReadinessResponse,
    CreateAiAgentRequest,
    UpdateAiAgentRequest,
    UpdateAiPolicyRequest,
)
from app.models.domain import ChannelType, Market


def _agent_response(record: AiAgentRecord) -> AiAgentResponse:
    return AiAgentResponse(
        id=record.id,
        market_id=record.market_id,
        name=record.name,
        description=record.description,
        instructions=record.instructions,
        status=cast(AiAgentStatus, record.status),
        channels=[ChannelType(channel) for channel in record.channels],
        languages=record.languages,
        handoff_team=record.handoff_team,
        confidence_threshold=record.confidence_threshold,
        auto_send=record.auto_send,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class AiStudioService:
    def _readiness(self, db: Session, *, market: Market) -> AiReadinessResponse:
        credentials = integration_credential_settings_repository.runtime_credentials(
            db,
            market_id=market.id,
        )
        workspace = get_or_create_workspace_settings(db, market)
        active_agents = db.scalar(
            select(func.count())
            .select_from(AiAgentRecord)
            .where(
                AiAgentRecord.market_id == market.id,
                AiAgentRecord.status == "active",
            )
        ) or 0
        configured = credentials.anthropic_api_key_configured
        return AiReadinessResponse(
            provider="Anthropic",
            configured=configured,
            model=credentials.anthropic_model,
            automation_enabled=workspace.ai_work_queue_automation_enabled,
            can_send_customer_messages=workspace.ai_can_send_customer_messages,
            active_agents=active_agents,
            detail=(
                "Anthropic credentials are configured for this market."
                if configured
                else "Anthropic is not configured. Add the API key in Admin credentials."
            ),
        )

    def readiness(self, db: Session, *, market: Market) -> AiReadinessResponse:
        result = self._readiness(db, market=market)
        db.commit()
        return result

    def list_agents(self, db: Session, *, market_id: str) -> list[AiAgentResponse]:
        records = db.scalars(
            select(AiAgentRecord)
            .where(AiAgentRecord.market_id == market_id)
            .order_by(AiAgentRecord.updated_at.desc())
        ).all()
        return [_agent_response(record) for record in records]

    def create_agent(
        self,
        db: Session,
        *,
        market_id: str,
        actor: str,
        request: CreateAiAgentRequest,
    ) -> AiAgentResponse:
        record = AiAgentRecord(
            id=f"ai_agent_{uuid4().hex}",
            market_id=market_id,
            name=request.name.strip(),
            description=request.description.strip(),
            instructions=request.instructions.strip(),
            status="draft",
            channels=[channel.value for channel in request.channels],
            languages=request.languages,
            handoff_team=request.handoff_team.strip(),
            confidence_threshold=request.confidence_threshold,
            auto_send=request.auto_send,
            created_by=actor,
        )
        db.add(record)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="An AI agent with this name already exists in the active market",
            ) from exc
        write_audit_event(
            db,
            actor=actor,
            action="ai_agent.create",
            entity_type="ai_agent",
            entity_id=record.id,
            market_id=market_id,
            details={
                "channels": record.channels,
                "languages": record.languages,
                "auto_send": record.auto_send,
            },
        )
        db.commit()
        db.refresh(record)
        return _agent_response(record)

    def _validate_activation(
        self,
        db: Session,
        *,
        market: Market,
        status_value: str,
        auto_send: bool,
    ) -> None:
        if status_value != "active":
            return
        readiness = self._readiness(db, market=market)
        if not readiness.configured:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Configure Anthropic credentials before activating this AI agent",
            )
        if not readiness.automation_enabled:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Enable AI automation before activating this AI agent",
            )
        if auto_send and not readiness.can_send_customer_messages:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Enable the audited customer auto-send policy before activating this agent",
            )

    def update_agent(
        self,
        db: Session,
        *,
        market: Market,
        actor: str,
        agent_id: str,
        request: UpdateAiAgentRequest,
    ) -> AiAgentResponse:
        record = db.get(AiAgentRecord, agent_id)
        if record is None or record.market_id != market.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="AI agent not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        next_status = str(patch.get("status", record.status))
        next_auto_send = bool(patch.get("auto_send", record.auto_send))
        self._validate_activation(
            db,
            market=market,
            status_value=next_status,
            auto_send=next_auto_send,
        )
        for key, value in patch.items():
            if key in {"name", "description", "instructions", "handoff_team"} and isinstance(
                value,
                str,
            ):
                value = value.strip()
            setattr(record, key, value)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="An AI agent with this name already exists in the active market",
            ) from exc
        write_audit_event(
            db,
            actor=actor,
            action="ai_agent.update",
            entity_type="ai_agent",
            entity_id=record.id,
            market_id=market.id,
            details={"changed_fields": sorted(patch)},
        )
        db.commit()
        db.refresh(record)
        return _agent_response(record)

    def update_policy(
        self,
        db: Session,
        *,
        market: Market,
        actor: str,
        request: UpdateAiPolicyRequest,
    ) -> AiReadinessResponse:
        patch = request.model_dump(exclude_unset=True)
        if not patch:
            return self.readiness(db, market=market)
        workspace = get_or_create_workspace_settings(db, market)
        if patch.get("can_send_customer_messages"):
            credentials = integration_credential_settings_repository.runtime_credentials(
                db,
                market_id=market.id,
            )
            if not credentials.anthropic_api_key_configured:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Configure Anthropic credentials before enabling customer auto-send",
                )
        if patch.get("automation_enabled") is False:
            active_agent = db.scalar(
                select(AiAgentRecord.id).where(
                    AiAgentRecord.market_id == market.id,
                    AiAgentRecord.status == "active",
                )
            )
            if active_agent is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Pause active AI agents before disabling AI automation",
                )
        if patch.get("can_send_customer_messages") is False:
            active_auto_send_agent = db.scalar(
                select(AiAgentRecord.id).where(
                    AiAgentRecord.market_id == market.id,
                    AiAgentRecord.status == "active",
                    AiAgentRecord.auto_send.is_(True),
                )
            )
            if active_auto_send_agent is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Pause active auto-send agents before disabling customer auto-send",
                )
        if "automation_enabled" in patch:
            workspace.ai_work_queue_automation_enabled = patch["automation_enabled"]
        if "can_send_customer_messages" in patch:
            workspace.ai_can_send_customer_messages = patch["can_send_customer_messages"]
        write_audit_event(
            db,
            actor=actor,
            action="ai_policy.update",
            entity_type="workspace_settings",
            entity_id=market.id,
            market_id=market.id,
            details=patch,
        )
        db.commit()
        return self.readiness(db, market=market)

    def list_decisions(
        self,
        db: Session,
        *,
        market_id: str,
        limit: int,
    ) -> list[AiDecisionResponse]:
        rows = db.execute(
            select(AiDecisionRecord, TicketRecord.public_id)
            .join(TicketRecord, TicketRecord.id == AiDecisionRecord.ticket_id)
            .where(AiDecisionRecord.market_id == market_id)
            .order_by(AiDecisionRecord.created_at.desc())
            .limit(limit)
        ).all()
        return [
            AiDecisionResponse(
                id=record.id,
                ticket_id=record.ticket_id,
                ticket_number=ticket_number,
                decision_type=record.decision_type,
                confidence=record.confidence,
                summary=record.summary,
                model_version=record.model_version,
                input_reference=record.input_reference,
                override_allowed=record.override_allowed,
                created_at=record.created_at,
            )
            for record, ticket_number in rows
        ]


ai_studio_service = AiStudioService()
