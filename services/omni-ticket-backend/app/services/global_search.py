from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentRecord,
    CompanyRecord,
    CustomerRecord,
    HandoffRecord,
    KnowledgeArticleRecord,
    SupportGroupRecord,
    TicketRecord,
)
from app.models.domain import GlobalSearchResult, GlobalSearchResultType


_TOKEN_STOPWORDS = {"and", "for", "from", "the", "this", "that", "with"}


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9@._-]+", value.lower())
        if len(token) >= 2 and token not in _TOKEN_STOPWORDS
    ]


def _score(query: str, *parts: object, exact_boost: bool = False) -> int:
    terms = _tokens(query)
    if not terms:
        return 0
    values = [str(part).lower() for part in parts if part]
    haystack = " ".join(values)
    score = 0
    for term in terms:
        if any(value == term for value in values):
            score += 45
        elif any(value.startswith(term) for value in values):
            score += 32
        elif term in haystack:
            score += 18
    if exact_boost and query.lower() in values:
        score += 30
    if all(term in haystack for term in terms):
        score += 12
    return min(score, 100)


def _result(
    *,
    result_type: GlobalSearchResultType,
    entity_id: str,
    title: str,
    subtitle: str,
    description: str,
    score: int,
    screen: str,
    metadata: dict,
) -> GlobalSearchResult:
    return GlobalSearchResult(
        id=f"{result_type.value}:{entity_id}",
        type=result_type,
        entity_id=entity_id,
        title=title,
        subtitle=subtitle,
        description=description,
        score=score,
        screen=screen,
        metadata=metadata,
    )


class GlobalSearchService:
    def search(
        self,
        db: Session,
        *,
        market_id: str,
        query: str,
        limit: int = 12,
    ) -> list[GlobalSearchResult]:
        term = query.strip()
        if len(term) < 2:
            return []

        customers = {
            customer.id: customer
            for customer in db.scalars(
                select(CustomerRecord).where(CustomerRecord.market_id == market_id)
            ).all()
        }
        companies = {
            company.id: company
            for company in db.scalars(
                select(CompanyRecord).where(CompanyRecord.market_id == market_id)
            ).all()
        }
        results: list[GlobalSearchResult] = []

        for ticket in db.scalars(select(TicketRecord).where(TicketRecord.market_id == market_id)).all():
            customer = customers.get(ticket.customer_id)
            score = _score(
                term,
                ticket.public_id,
                ticket.subject,
                ticket.description,
                ticket.status,
                ticket.priority,
                ticket.channel,
                ticket.team,
                ticket.ai_summary,
                ticket.recommended_action,
                " ".join(ticket.tags or []),
                customer.name if customer else "",
                customer.email if customer else "",
                exact_boost=True,
            )
            if score:
                results.append(
                    _result(
                        result_type=GlobalSearchResultType.ticket,
                        entity_id=ticket.id,
                        title=f"{ticket.public_id} · {ticket.subject}",
                        subtitle=f"{ticket.status} · {ticket.priority} · {ticket.team}",
                        description=ticket.description[:220],
                        score=min(score + 6, 100),
                        screen="inbox",
                        metadata={
                            "public_id": ticket.public_id,
                            "customer_id": ticket.customer_id,
                            "customer_name": customer.name if customer else None,
                            "status": ticket.status,
                            "priority": ticket.priority,
                        },
                    )
                )

        for customer in customers.values():
            company = companies.get(customer.company_id or "")
            score = _score(
                term,
                customer.name,
                customer.email,
                customer.location,
                customer.sentiment,
                customer.notes,
                " ".join(customer.tags or []),
                company.name if company else "",
                exact_boost=True,
            )
            if score:
                results.append(
                    _result(
                        result_type=GlobalSearchResultType.customer,
                        entity_id=customer.id,
                        title=customer.name,
                        subtitle=customer.email,
                        description=customer.notes[:220],
                        score=min(score + 4, 100),
                        screen="customers",
                        metadata={
                            "company_id": customer.company_id,
                            "company_name": company.name if company else None,
                            "sentiment": customer.sentiment,
                        },
                    )
                )

        for company in companies.values():
            score = _score(term, company.name, company.tier, company.health_score, company.account_value)
            if score:
                results.append(
                    _result(
                        result_type=GlobalSearchResultType.company,
                        entity_id=company.id,
                        title=company.name,
                        subtitle=f"{company.tier} account",
                        description=f"Health {company.health_score} · Value {company.account_value}",
                        score=score,
                        screen="customers",
                        metadata={"tier": company.tier},
                    )
                )

        for article in db.scalars(select(KnowledgeArticleRecord)).all():
            if market_id not in article.market_ids:
                continue
            score = _score(
                term,
                article.title,
                article.body,
                article.status,
                article.language,
                " ".join(article.tags or []),
            )
            if score:
                results.append(
                    _result(
                        result_type=GlobalSearchResultType.knowledge,
                        entity_id=article.id,
                        title=article.title,
                        subtitle=f"{article.status} · {article.language}",
                        description=article.body[:220],
                        score=score,
                        screen="knowledge",
                        metadata={"status": article.status, "tags": article.tags},
                    )
                )

        for group in db.scalars(select(SupportGroupRecord).where(SupportGroupRecord.market_id == market_id)).all():
            score = _score(
                term,
                group.name,
                group.description,
                group.team_email,
                " ".join(group.channels or []),
                " ".join(group.skills or []),
                exact_boost=True,
            )
            if score:
                results.append(
                    _result(
                        result_type=GlobalSearchResultType.support_group,
                        entity_id=group.id,
                        title=group.name,
                        subtitle=group.team_email or "No team inbox set",
                        description=group.description,
                        score=score,
                        screen="admin",
                        metadata={"active": group.active, "channels": group.channels},
                    )
                )

        for handoff in db.scalars(select(HandoffRecord).where(HandoffRecord.market_id == market_id)).all():
            handoff_ticket = db.get(TicketRecord, handoff.ticket_id)
            score = _score(
                term,
                handoff.from_team,
                handoff.to_team,
                handoff.requested_by,
                handoff.reason,
                handoff.status,
                handoff_ticket.public_id if handoff_ticket else "",
                handoff_ticket.subject if handoff_ticket else "",
            )
            if score:
                results.append(
                    _result(
                        result_type=GlobalSearchResultType.handoff,
                        entity_id=handoff.id,
                        title=f"{handoff.to_team} handoff",
                        subtitle=f"{handoff.status} · {handoff_ticket.public_id if handoff_ticket else handoff.ticket_id}",
                        description=handoff.reason,
                        score=score,
                        screen="handoffs",
                        metadata={"ticket_id": handoff.ticket_id, "status": handoff.status},
                    )
                )

        for agent in db.scalars(select(AgentRecord)).all():
            if market_id not in agent.market_ids:
                continue
            score = _score(
                term,
                agent.name,
                agent.email,
                agent.role,
                agent.status,
                " ".join(agent.skills or []),
                " ".join(agent.languages or []),
                exact_boost=True,
            )
            if score:
                results.append(
                    _result(
                        result_type=GlobalSearchResultType.agent,
                        entity_id=agent.id,
                        title=agent.name,
                        subtitle=f"{agent.role} · {agent.status}",
                        description=agent.email,
                        score=score,
                        screen="workforce",
                        metadata={"occupancy": agent.occupancy, "capacity": agent.capacity},
                    )
                )

        results.sort(key=lambda item: (-item.score, item.type.value, item.title.lower()))
        return results[:limit]


global_search_service = GlobalSearchService()
