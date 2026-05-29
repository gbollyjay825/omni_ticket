from copy import deepcopy
from datetime import timedelta
from threading import RLock
from uuid import uuid4

from app.models.domain import (
    Agent,
    AgentStatus,
    AiDecision,
    AuditEvent,
    AutomationRule,
    Channel,
    ChannelHealth,
    ChannelType,
    Company,
    ConnectorDirection,
    ConnectorEvent,
    ContactPoint,
    Customer,
    Handoff,
    HandoffStatus,
    KnowledgeArticle,
    Market,
    OutboundMessage,
    Priority,
    Sentiment,
    Ticket,
    TicketStatus,
    TicketTask,
    TimelineEvent,
    TimelineEventType,
    User,
    UserRole,
    WorkspaceSettings,
    default_sla,
    utc_now,
)


class InMemoryStore:
    """Thread-safe local store used until the PostgreSQL repository is attached."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.settings = WorkspaceSettings()
        self.settings_by_market: dict[str, WorkspaceSettings] = {}
        self.markets: dict[str, Market] = {}
        self.users: dict[str, User] = {}
        self.sessions: dict[str, str] = {}
        self.channels: dict[str, Channel] = {}
        self.agents: dict[str, Agent] = {}
        self.companies: dict[str, Company] = {}
        self.customers: dict[str, Customer] = {}
        self.tickets: dict[str, Ticket] = {}
        self.timeline: dict[str, list[TimelineEvent]] = {}
        self.handoffs: dict[str, Handoff] = {}
        self.knowledge: dict[str, KnowledgeArticle] = {}
        self.rules: dict[str, AutomationRule] = {}
        self.connector_events: dict[str, ConnectorEvent] = {}
        self.outbound_messages: dict[str, OutboundMessage] = {}
        self.audit: list[AuditEvent] = []
        self.ai_decisions: list[AiDecision] = []
        self._ticket_sequence = 1000
        self.seed()

    def seed(self) -> None:
        with self._lock:
            self.markets = {
                "market-ng": Market(
                    id="market-ng",
                    code="NG",
                    name="Nigeria",
                    timezone="Africa/Lagos",
                    currency="NGN",
                    support_email="support.ng@example.com",
                    whatsapp_number="+23480006664",
                    facebook_page="@omniticketng",
                    instagram_handle="@omniticketng",
                ),
                "market-gh": Market(
                    id="market-gh",
                    code="GH",
                    name="Ghana",
                    timezone="Africa/Accra",
                    currency="GHS",
                    support_email="support.gh@example.com",
                    whatsapp_number="+23330006664",
                    facebook_page="@omniticketgh",
                    instagram_handle="@omniticketgh",
                ),
                "market-uk": Market(
                    id="market-uk",
                    code="UK",
                    name="United Kingdom",
                    timezone="Europe/London",
                    currency="GBP",
                    support_email="support.uk@example.com",
                    whatsapp_number="+447700900664",
                    facebook_page="@omniticketuk",
                    instagram_handle="@omniticketuk",
                ),
            }
            self.settings_by_market = {
                market_id: WorkspaceSettings(
                    market_id=market_id,
                    default_timezone=market.timezone,
                    public_brand_name=f"Omni Ticket {market.code}",
                )
                for market_id, market in self.markets.items()
            }
            self.settings = self.settings_by_market["market-ng"]
            self.users = {
                "user-gbolahan": User(
                    id="user-gbolahan",
                    name="Gbolahan Salami",
                    email="gbolahan@omniticket.example.com",
                    role=UserRole.admin,
                    market_ids=["market-ng", "market-gh", "market-uk"],
                    default_market_id="market-ng",
                ),
                "user-ng-agent": User(
                    id="user-ng-agent",
                    name="Amara Market Admin",
                    email="amara.ng@omniticket.example.com",
                    role=UserRole.supervisor,
                    market_ids=["market-ng"],
                    default_market_id="market-ng",
                ),
                "user-gh-agent": User(
                    id="user-gh-agent",
                    name="Kofi Mensah",
                    email="kofi.gh@omniticket.example.com",
                    role=UserRole.agent,
                    market_ids=["market-gh"],
                    default_market_id="market-gh",
                ),
            }
            self.sessions = {}
            self.channels = {
                "channel-email": Channel(
                    id="channel-email",
                    market_id="market-ng",
                    type=ChannelType.email,
                    name="Nigeria support mailbox",
                    handle="support.ng@example.com",
                    queued=38,
                    active=12,
                    sla_risk=5,
                    capabilities=["inbound", "outbound", "attachments", "threading"],
                ),
                "channel-whatsapp": Channel(
                    id="channel-whatsapp",
                    market_id="market-ng",
                    type=ChannelType.whatsapp,
                    name="Nigeria WhatsApp Business",
                    handle="+234-800-OMNI",
                    queued=32,
                    active=20,
                    sla_risk=4,
                    capabilities=["inbound", "outbound", "templates", "media", "receipts"],
                ),
                "channel-facebook": Channel(
                    id="channel-facebook",
                    market_id="market-ng",
                    type=ChannelType.facebook,
                    name="Nigeria Facebook Messenger",
                    handle="@omniticketng",
                    queued=9,
                    active=5,
                    sla_risk=1,
                    capabilities=["page-webhook", "private-reply", "receipts"],
                ),
                "channel-instagram": Channel(
                    id="channel-instagram",
                    market_id="market-ng",
                    type=ChannelType.instagram,
                    name="Nigeria Instagram DM",
                    handle="@omniticketng",
                    health=ChannelHealth.degraded,
                    queued=14,
                    active=9,
                    sla_risk=6,
                    capabilities=["dm", "comment-to-dm", "media"],
                ),
                "channel-voice": Channel(
                    id="channel-voice",
                    market_id="market-ng",
                    type=ChannelType.voice,
                    name="Phone and voice",
                    handle="+234-800-CALL",
                    queued=11,
                    active=8,
                    sla_risk=2,
                    capabilities=["call-log", "callback", "voicemail-summary"],
                ),
                "channel-api": Channel(
                    id="channel-api",
                    market_id="market-ng",
                    type=ChannelType.api,
                    name="Partner API",
                    handle="api.omniticket.local",
                    queued=7,
                    active=4,
                    sla_risk=1,
                    capabilities=["webhook", "idempotency", "replay-protection"],
                ),
                "channel-gh-whatsapp": Channel(
                    id="channel-gh-whatsapp",
                    market_id="market-gh",
                    type=ChannelType.whatsapp,
                    name="Ghana WhatsApp Business",
                    handle="+233-300-OMNI",
                    queued=12,
                    active=7,
                    sla_risk=2,
                    capabilities=["inbound", "outbound", "templates", "media", "receipts"],
                ),
                "channel-uk-email": Channel(
                    id="channel-uk-email",
                    market_id="market-uk",
                    type=ChannelType.email,
                    name="UK support mailbox",
                    handle="support.uk@example.com",
                    queued=18,
                    active=6,
                    sla_risk=1,
                    capabilities=["inbound", "outbound", "attachments", "threading"],
                ),
            }

            self.agents = {
                "agent-amara": Agent(
                    id="agent-amara",
                    market_ids=["market-ng"],
                    name="Amara Lee",
                    email="amara@example.com",
                    team="Billing Support",
                    status=AgentStatus.available,
                    occupancy=69,
                    skills=[ChannelType.email, ChannelType.portal, ChannelType.api],
                ),
                "agent-noah": Agent(
                    id="agent-noah",
                    market_ids=["market-ng"],
                    name="Noah Chen",
                    email="noah@example.com",
                    team="Chat Care",
                    status=AgentStatus.busy,
                    occupancy=90,
                    skills=[ChannelType.whatsapp, ChannelType.sms, ChannelType.portal],
                ),
                "agent-mateo": Agent(
                    id="agent-mateo",
                    market_ids=["market-ng", "market-gh"],
                    name="Mateo Ruiz",
                    email="mateo@example.com",
                    team="Social Care",
                    status=AgentStatus.away,
                    occupancy=87,
                    skills=[ChannelType.facebook, ChannelType.instagram],
                ),
                "agent-zara": Agent(
                    id="agent-zara",
                    market_ids=["market-ng", "market-uk"],
                    name="Zara Okafor",
                    email="zara@example.com",
                    team="Escalations",
                    status=AgentStatus.available,
                    occupancy=50,
                    skills=[ChannelType.voice, ChannelType.internal, ChannelType.api],
                ),
                "agent-kofi": Agent(
                    id="agent-kofi",
                    market_ids=["market-gh"],
                    name="Kofi Mensah",
                    email="kofi.gh@omniticket.example.com",
                    team="Ghana Care",
                    status=AgentStatus.available,
                    occupancy=52,
                    skills=[ChannelType.whatsapp, ChannelType.email, ChannelType.facebook],
                ),
            }

            self.companies = {
                "company-solace": Company(
                    id="company-solace",
                    market_id="market-ng",
                    name="Solace Home",
                    tier="premium",
                    health_score=44,
                    account_value=820,
                ),
                "company-bluebird": Company(
                    id="company-bluebird",
                    market_id="market-uk",
                    name="Bluebird Retail",
                    tier="growth",
                    health_score=68,
                    account_value=540,
                ),
                "company-lattice": Company(
                    id="company-lattice",
                    market_id="market-ng",
                    name="Lattice Logistics",
                    tier="enterprise",
                    health_score=61,
                    account_value=1260,
                ),
                "company-accra": Company(
                    id="company-accra",
                    market_id="market-gh",
                    name="Accra Retail Co",
                    tier="growth",
                    health_score=72,
                    account_value=420,
                ),
            }

            self.customers = {
                "cust-sofia": Customer(
                    id="cust-sofia",
                    market_id="market-ng",
                    name="Sofia Grant",
                    email="sofia.grant@example.com",
                    company_id="company-solace",
                    location="New York, NY",
                    sentiment=Sentiment.frustrated,
                    preferred_channels=[ChannelType.facebook, ChannelType.instagram],
                    contact_points=[
                        ContactPoint(channel=ChannelType.email, value="sofia.grant@example.com"),
                        ContactPoint(channel=ChannelType.facebook, value="fb:sofia.grant"),
                        ContactPoint(channel=ChannelType.instagram, value="@sofiagrant"),
                    ],
                    tags=["delivery-risk", "reputation-risk"],
                    notes="Shared order screenshots after a missed delivery complaint.",
                ),
                "cust-maya": Customer(
                    id="cust-maya",
                    market_id="market-uk",
                    name="Maya Roberts",
                    email="maya.roberts@example.com",
                    company_id="company-bluebird",
                    location="London, UK",
                    sentiment=Sentiment.neutral,
                    preferred_channels=[ChannelType.email, ChannelType.portal],
                    contact_points=[
                        ContactPoint(channel=ChannelType.email, value="maya.roberts@example.com"),
                        ContactPoint(channel=ChannelType.whatsapp, value="+447700900123"),
                    ],
                    tags=["billing"],
                ),
                "cust-leo": Customer(
                    id="cust-leo",
                    market_id="market-ng",
                    name="Leo Ahmed",
                    email="leo.ahmed@example.com",
                    company_id="company-lattice",
                    location="Lagos, NG",
                    sentiment=Sentiment.angry,
                    preferred_channels=[ChannelType.whatsapp, ChannelType.sms],
                    contact_points=[
                        ContactPoint(channel=ChannelType.whatsapp, value="+2348012345678"),
                        ContactPoint(channel=ChannelType.sms, value="+2348012345678"),
                    ],
                    tags=["payment-risk", "mobile"],
                ),
                "cust-ama": Customer(
                    id="cust-ama",
                    market_id="market-gh",
                    name="Ama Boateng",
                    email="ama.boateng@example.com",
                    company_id="company-accra",
                    location="Accra, GH",
                    sentiment=Sentiment.neutral,
                    preferred_channels=[ChannelType.whatsapp, ChannelType.email],
                    contact_points=[
                        ContactPoint(channel=ChannelType.whatsapp, value="+233301234567"),
                        ContactPoint(channel=ChannelType.email, value="ama.boateng@example.com"),
                    ],
                    tags=["ghana-market"],
                ),
            }

            self.knowledge = {
                "article-social-playbook": KnowledgeArticle(
                    id="article-social-playbook",
                    market_ids=["market-ng", "market-gh", "market-uk"],
                    title="Social complaint handling playbook",
                    channels=[ChannelType.facebook, ChannelType.instagram],
                    tags=["social", "complaint", "reputation-risk"],
                    body="Move private details to DM, keep public acknowledgement neutral, and close the loop.",
                ),
                "article-duplicate-payment": KnowledgeArticle(
                    id="article-duplicate-payment",
                    market_ids=["market-ng", "market-gh", "market-uk"],
                    title="Duplicate payment reversal checklist",
                    channels=[ChannelType.email, ChannelType.whatsapp, ChannelType.portal],
                    tags=["billing", "payment-risk"],
                    body="Confirm transaction reference, payment gateway state, and reversal SLA before replying.",
                ),
            }

            self.rules = {
                "rule-social-risk": AutomationRule(
                    id="rule-social-risk",
                    market_id="market-ng",
                    name="Escalate social complaints near SLA breach",
                    trigger="channel in facebook,instagram and sentiment in frustrated,angry",
                    action="raise priority, assign Social Care, notify supervisor",
                ),
                "rule-payment-risk": AutomationRule(
                    id="rule-payment-risk",
                    market_id="market-ng",
                    name="Route duplicate payments to billing specialists",
                    trigger="intent contains payment or duplicate",
                    action="assign Billing Support and attach duplicate payment checklist",
                ),
            }

            self.tickets = {}
            self.timeline = {}
            self.handoffs = {}
            self.connector_events = {}
            self.audit = []
            self.ai_decisions = []
            self._ticket_sequence = 1000

            self._seed_ticket(
                market_id="market-ng",
                subject="Public complaint about missed delivery",
                description="Customer posted publicly and sent order screenshots by DM.",
                customer_id="cust-sofia",
                channel=ChannelType.instagram,
                priority=Priority.urgent,
                sentiment=Sentiment.frustrated,
                assignee_id="agent-mateo",
                team="Social Care",
                tags=["instagram", "delivery", "reputation-risk", "ai-routed"],
                summary="Public social complaint with private order details moved into DM.",
                action="Reply in DM and keep the public acknowledgement neutral.",
            )
            self._seed_ticket(
                market_id="market-uk",
                subject="Invoice adjustment was promised but not reflected",
                description="Customer says the revised invoice still shows the original disputed charge.",
                customer_id="cust-maya",
                channel=ChannelType.email,
                priority=Priority.high,
                sentiment=Sentiment.frustrated,
                assignee_id="agent-amara",
                team="Billing Support",
                tags=["billing", "invoice", "promise-risk", "ai-routed"],
                summary="Billing promise needs a clear owner and invoice correction timeline.",
                action="Confirm adjustment status and send corrected invoice or ETA.",
            )
            self._seed_ticket(
                market_id="market-ng",
                subject="Duplicate payment shown after mobile checkout",
                description="Customer screenshots show two payment holds after mobile checkout.",
                customer_id="cust-leo",
                channel=ChannelType.whatsapp,
                priority=Priority.high,
                sentiment=Sentiment.angry,
                assignee_id="agent-noah",
                team="Chat Care",
                tags=["whatsapp", "payment-risk", "mobile", "ai-routed"],
                summary="Likely payment authorization duplicate requiring billing confirmation.",
                action="Confirm transaction reference and start duplicate payment reversal checklist.",
            )
            self._seed_ticket(
                market_id="market-gh",
                subject="WhatsApp refund status request",
                description="Customer in Ghana asked for refund status after a mobile money hold.",
                customer_id="cust-ama",
                channel=ChannelType.whatsapp,
                priority=Priority.high,
                sentiment=Sentiment.frustrated,
                assignee_id="agent-kofi",
                team="Ghana Care",
                tags=["ghana-market", "payment-risk", "ai-routed"],
                summary="Ghana WhatsApp refund request needs payment confirmation and timeline.",
                action="Confirm mobile money reference and send refund ETA.",
            )

    def _seed_ticket(
        self,
        *,
        market_id: str,
        subject: str,
        description: str,
        customer_id: str,
        channel: ChannelType,
        priority: Priority,
        sentiment: Sentiment,
        assignee_id: str,
        team: str,
        tags: list[str],
        summary: str,
        action: str,
    ) -> Ticket:
        ticket = self.create_ticket_record(
            subject=subject,
            market_id=market_id,
            description=description,
            customer_id=customer_id,
            channel=channel,
            priority=priority,
            sentiment=sentiment,
            assignee_id=assignee_id,
            team=team,
            tags=tags,
            ai_summary=summary,
            recommended_action=action,
        )
        self.timeline[ticket.id] = [
            TimelineEvent(
                id=self.next_id("event"),
                ticket_id=ticket.id,
                type=TimelineEventType.inbound,
                channel=channel,
                actor=self.customers[customer_id].name,
                body=description,
                public=True,
            ),
            TimelineEvent(
                id=self.next_id("event"),
                ticket_id=ticket.id,
                type=TimelineEventType.ai_decision,
                channel=ChannelType.internal,
                actor="AI Work Queue",
                body=action,
                public=False,
                metadata={"summary": summary, "priority": priority.value},
            ),
        ]
        return ticket

    def next_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:10]}"

    def next_public_ticket_id(self) -> str:
        self._ticket_sequence += 1
        return f"OMNI-{self._ticket_sequence}"

    def create_ticket_record(
        self,
        *,
        market_id: str,
        subject: str,
        description: str,
        customer_id: str,
        channel: ChannelType,
        priority: Priority,
        sentiment: Sentiment,
        assignee_id: str | None,
        team: str,
        tags: list[str],
        ai_summary: str,
        recommended_action: str,
    ) -> Ticket:
        now = utc_now()
        ticket = Ticket(
            id=self.next_id("ticket"),
            market_id=market_id,
            public_id=self.next_public_ticket_id(),
            subject=subject,
            description=description,
            customer_id=customer_id,
            channel=channel,
            status=TicketStatus.open,
            priority=priority,
            sentiment=sentiment,
            assignee_id=assignee_id,
            team=team,
            tags=tags,
            tasks=[
                TicketTask(id=self.next_id("task"), label="Acknowledge customer"),
                TicketTask(id=self.next_id("task"), label="Clear blocker"),
                TicketTask(id=self.next_id("task"), label="Close promise"),
            ],
            sla=default_sla(priority, now),
            ai_summary=ai_summary,
            recommended_action=recommended_action,
            created_at=now,
            updated_at=now,
        )
        self.tickets[ticket.id] = ticket
        self.timeline.setdefault(ticket.id, [])
        return ticket

    def snapshot(self) -> "InMemoryStore":
        return deepcopy(self)

    def settings_for(self, market_id: str) -> WorkspaceSettings:
        if market_id not in self.settings_by_market:
            self.settings_by_market[market_id] = WorkspaceSettings(market_id=market_id)
        return self.settings_by_market[market_id]

    def create_session(self, user_id: str) -> str:
        token = f"ot_{uuid4().hex}"
        self.sessions[token] = user_id
        return token

    def user_for_token(self, token: str) -> User | None:
        user_id = self.sessions.get(token)
        if not user_id:
            return None
        return self.users.get(user_id)

    def audit_event(
        self,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        market_id: str | None = None,
        details: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=self.next_id("audit"),
            market_id=market_id,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
        self.audit.append(event)
        return event

    def append_timeline(self, event: TimelineEvent) -> TimelineEvent:
        with self._lock:
            self.timeline.setdefault(event.ticket_id, []).append(event)
            if event.ticket_id in self.tickets:
                self.tickets[event.ticket_id].updated_at = utc_now()
            self.audit_event(
                actor=event.actor,
                action=f"timeline.{event.type.value}",
                entity_type="ticket",
                entity_id=event.ticket_id,
                market_id=self.tickets[event.ticket_id].market_id
                if event.ticket_id in self.tickets
                else None,
                details={"channel": event.channel.value, "public": event.public},
            )
            return event

    def create_handoff(
        self,
        *,
        ticket_id: str,
        market_id: str,
        from_team: str,
        to_team: str,
        requested_by: str,
        reason: str,
        due_minutes: int,
        checklist: list[str],
    ) -> Handoff:
        with self._lock:
            handoff = Handoff(
                id=self.next_id("handoff"),
                market_id=market_id,
                ticket_id=ticket_id,
                from_team=from_team,
                to_team=to_team,
                requested_by=requested_by,
                reason=reason,
                due_at=utc_now() + timedelta(minutes=due_minutes),
                checklist=[
                    TicketTask(id=self.next_id("task"), label=item, complete=False)
                    for item in checklist
                ],
            )
            self.handoffs[handoff.id] = handoff
            self.append_timeline(
                TimelineEvent(
                    id=self.next_id("event"),
                    ticket_id=ticket_id,
                    type=TimelineEventType.handoff_requested,
                    channel=ChannelType.internal,
                    actor=requested_by,
                    body=f"Handoff requested for {to_team}: {reason}",
                    public=False,
                    metadata={"handoff_id": handoff.id},
                )
            )
            return handoff

    def update_handoff_status(
        self,
        handoff_id: str,
        *,
        status: HandoffStatus | None,
        blocker: str | None,
        checklist_item_id: str | None,
        checklist_item_complete: bool | None,
    ) -> Handoff | None:
        with self._lock:
            handoff = self.handoffs.get(handoff_id)
            if handoff is None:
                return None
            if status is not None:
                handoff.status = status
            if blocker is not None:
                handoff.blocker = blocker
                handoff.status = HandoffStatus.blocked
            if checklist_item_id and checklist_item_complete is not None:
                for item in handoff.checklist:
                    if item.id == checklist_item_id:
                        item.complete = checklist_item_complete
                        break
            handoff.updated_at = utc_now()
            event_type = (
                TimelineEventType.handoff_resolved
                if handoff.status == HandoffStatus.resolved
                else TimelineEventType.status_change
            )
            self.append_timeline(
                TimelineEvent(
                    id=self.next_id("event"),
                    ticket_id=handoff.ticket_id,
                    type=event_type,
                    channel=ChannelType.internal,
                    actor="handoff-service",
                    body=f"Handoff {handoff.status.value}: {handoff.to_team}",
                    public=False,
                    metadata={"handoff_id": handoff.id, "blocker": handoff.blocker},
                )
            )
            return handoff

    def record_connector_event(
        self,
        *,
        market_id: str,
        provider: ChannelType,
        direction: ConnectorDirection,
        external_id: str,
        ticket_id: str | None,
        status: str,
        payload: dict,
    ) -> ConnectorEvent:
        event = ConnectorEvent(
            id=self.next_id("connector"),
            market_id=market_id,
            provider=provider,
            direction=direction,
            external_id=external_id,
            ticket_id=ticket_id,
            status=status,
            payload=payload,
        )
        self.connector_events[event.id] = event
        return event


store = InMemoryStore()
