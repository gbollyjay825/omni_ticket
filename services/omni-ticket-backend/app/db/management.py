from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store import InMemoryStore
from app.db.mappers import (
    agent_from_record,
    audit_event_from_record,
    automation_rule_from_record,
    channel_from_record,
    knowledge_article_from_record,
)
from app.db.models import (
    AgentRecord,
    AuditEventRecord,
    AutomationRuleRecord,
    ChannelRecord,
    KnowledgeArticleRecord,
)
from app.models.domain import (
    Agent,
    AutomationRule,
    Channel,
    CreateAutomationRuleRequest,
    CreateKnowledgeArticleRequest,
    KnowledgeArticle,
    UpdateAgentStatusRequest,
    UpdateAutomationRuleRequest,
    UpdateChannelRequest,
    UpdateKnowledgeArticleRequest,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _audit(
    db: Session,
    state: InMemoryStore,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    market_id: str,
    details: dict,
) -> None:
    record = AuditEventRecord(
        id=_new_id("audit"),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        market_id=market_id,
        details=details,
    )
    db.add(record)
    db.flush()
    state.audit.append(audit_event_from_record(record))


class ManagementRepository:
    def list_channels(self, db: Session, state: InMemoryStore, market_id: str) -> list[Channel]:
        channels = [
            channel_from_record(record)
            for record in db.scalars(
                select(ChannelRecord).where(ChannelRecord.market_id == market_id)
            ).all()
        ]
        state.channels = {
            **{key: value for key, value in state.channels.items() if value.market_id != market_id},
            **{channel.id: channel for channel in channels},
        }
        return channels

    def update_channel(
        self,
        db: Session,
        state: InMemoryStore,
        channel_id: str,
        request: UpdateChannelRequest,
        market_id: str,
    ) -> Channel:
        record = db.get(ChannelRecord, channel_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Channel not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        for key, value in patch.items():
            if value is not None:
                setattr(record, key, value)
        _audit(
            db,
            state,
            actor="api",
            action="channel.update",
            entity_type="channel",
            entity_id=channel_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        channel = channel_from_record(record)
        state.channels[channel.id] = channel
        return channel

    def list_agents(self, db: Session, state: InMemoryStore, market_id: str) -> list[Agent]:
        agents = [
            agent_from_record(record)
            for record in db.scalars(select(AgentRecord)).all()
            if market_id in record.market_ids
        ]
        state.agents = {
            **{key: value for key, value in state.agents.items() if market_id not in value.market_ids},
            **{agent.id: agent for agent in agents},
        }
        return agents

    def update_agent_status(
        self,
        db: Session,
        state: InMemoryStore,
        agent_id: str,
        request: UpdateAgentStatusRequest,
        market_id: str,
    ) -> Agent:
        record = db.get(AgentRecord, agent_id)
        if record is None or market_id not in record.market_ids:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agent not found")
        record.status = request.status.value
        _audit(
            db,
            state,
            actor="api",
            action="agent.status.update",
            entity_type="agent",
            entity_id=agent_id,
            market_id=market_id,
            details={"status": request.status.value},
        )
        db.commit()
        db.refresh(record)
        agent = agent_from_record(record)
        state.agents[agent.id] = agent
        return agent

    def list_knowledge(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[KnowledgeArticle]:
        articles = [
            knowledge_article_from_record(record)
            for record in db.scalars(select(KnowledgeArticleRecord)).all()
            if market_id in record.market_ids
        ]
        state.knowledge = {
            **{
                key: value
                for key, value in state.knowledge.items()
                if market_id not in value.market_ids
            },
            **{article.id: article for article in articles},
        }
        return articles

    def create_knowledge_article(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateKnowledgeArticleRequest,
        market_id: str,
    ) -> KnowledgeArticle:
        payload = request.model_dump(mode="json")
        payload["market_ids"] = payload["market_ids"] or [market_id]
        record = KnowledgeArticleRecord(id=_new_id("article"), **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor="api",
            action="knowledge.create",
            entity_type="knowledge_article",
            entity_id=record.id,
            market_id=market_id,
            details={"title": record.title},
        )
        db.commit()
        db.refresh(record)
        article = knowledge_article_from_record(record)
        state.knowledge[article.id] = article
        return article

    def update_knowledge_article(
        self,
        db: Session,
        state: InMemoryStore,
        article_id: str,
        request: UpdateKnowledgeArticleRequest,
        market_id: str,
    ) -> KnowledgeArticle:
        record = db.get(KnowledgeArticleRecord, article_id)
        if record is None or market_id not in record.market_ids:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge article not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        for key, value in patch.items():
            if value is not None:
                setattr(record, key, value)
        _audit(
            db,
            state,
            actor="api",
            action="knowledge.update",
            entity_type="knowledge_article",
            entity_id=article_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        article = knowledge_article_from_record(record)
        state.knowledge[article.id] = article
        return article

    def list_automation_rules(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[AutomationRule]:
        rules = [
            automation_rule_from_record(record)
            for record in db.scalars(
                select(AutomationRuleRecord).where(AutomationRuleRecord.market_id == market_id)
            ).all()
        ]
        state.rules = {
            **{key: value for key, value in state.rules.items() if value.market_id != market_id},
            **{rule.id: rule for rule in rules},
        }
        return rules

    def create_automation_rule(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateAutomationRuleRequest,
        market_id: str,
    ) -> AutomationRule:
        payload = request.model_dump(mode="json")
        payload["market_id"] = market_id
        record = AutomationRuleRecord(id=_new_id("rule"), **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor="api",
            action="automation_rule.create",
            entity_type="automation_rule",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name},
        )
        db.commit()
        db.refresh(record)
        rule = automation_rule_from_record(record)
        state.rules[rule.id] = rule
        return rule

    def update_automation_rule(
        self,
        db: Session,
        state: InMemoryStore,
        rule_id: str,
        request: UpdateAutomationRuleRequest,
        market_id: str,
    ) -> AutomationRule:
        record = db.get(AutomationRuleRecord, rule_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Automation rule not found")
        patch = request.model_dump(exclude_unset=True, mode="json")
        for key, value in patch.items():
            if value is not None:
                setattr(record, key, value)
        _audit(
            db,
            state,
            actor="api",
            action="automation_rule.update",
            entity_type="automation_rule",
            entity_id=rule_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        rule = automation_rule_from_record(record)
        state.rules[rule.id] = rule
        return rule


management_repository = ManagementRepository()
