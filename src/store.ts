import { useEffect, useMemo, useState } from 'react'
import { openDB, type DBSchema } from 'idb'
import type {
  AgentProfile,
  Channel,
  ChannelId,
  ComposerInput,
  ConversationStatus,
  CustomerProfile,
  HandoffStatus,
  InboxFilters,
  KnowledgeArticle,
  NewTicketInput,
  OmniConversation,
  OmniState,
  Priority,
  RuleStatus,
  ScreenId,
  Sentiment,
  SlaState,
  TimelineEvent,
  TimelineType,
  WorkspaceSettings,
} from './domain'
import {
  type BackendAgent,
  changeBackendPassword,
  createBackendUser,
  createBackendHandoff,
  createBackendTicket,
  type BackendAutomationRule,
  type BackendChannel,
  type BackendCompany,
  type BackendCreateUserInput,
  type BackendCustomer,
  type BackendHandoff,
  type BackendKnowledgeArticle,
  fetchBackendSnapshot,
  getBackendBaseUrl,
  loginBackend,
  patchBackendAutomationRule,
  patchBackendChannel,
  patchBackendHandoff,
  patchBackendKnowledgeArticle,
  patchBackendSettings,
  patchBackendTicket,
  patchBackendUser,
  type BackendLoginInput,
  type BackendSession,
  type BackendSyncState,
  type BackendUpdateUserInput,
  type BackendTicket,
  type BackendTicketContext,
  type BackendTimelineEvent,
  type BackendSnapshot,
  postBackendReply,
  retryBackendOutboundMessage,
} from './backend'
import { initialOmniState } from './seed'

interface TicketDeskDb extends DBSchema {
  state: {
    key: string
    value: OmniState
  }
}

const dbName = 'omni-ticket'
const stateKey = 'state-v17'
const backendSessionKey = 'omni-ticket-backend-session'
const screenIds: ScreenId[] = [
  'command',
  'inbox',
  'channels',
  'customers',
  'knowledge',
  'automation',
  'handoffs',
  'analytics',
  'workforce',
  'admin',
  'tracker',
]
const channelIds: (ChannelId | 'all')[] = [
  'all',
  'email',
  'chat',
  'phone',
  'whatsapp',
  'sms',
  'instagram',
  'facebook',
  'portal',
  'api',
  'internal',
]

type RouteUpdate = {
  screen?: ScreenId
  channel?: ChannelId | 'all' | null
  conversation?: string | null
  customer?: string | null
}

function routeStateFromUrl(state: OmniState) {
  if (typeof window === 'undefined') return state
  const params = new URLSearchParams(window.location.search)
  const screen = params.get('screen')
  const channel = params.get('channel')
  const conversationId = params.get('conversation')
  const customerId = params.get('customer')
  const conversation = state.conversations.find((item) => item.id === conversationId)
  const customer = state.customers.find((item) => item.id === customerId)
  const routeChannel = channelIds.includes(channel as ChannelId | 'all')
    ? (channel as ChannelId | 'all')
    : undefined

  return {
    ...state,
    selectedScreen: screenIds.includes(screen as ScreenId) ? (screen as ScreenId) : state.selectedScreen,
    selectedChannelId: routeChannel ?? state.selectedChannelId,
    filters: routeChannel ? { ...state.filters, channel: routeChannel } : state.filters,
    selectedConversationId: conversation?.id ?? state.selectedConversationId,
    selectedCustomerId: customer?.id ?? conversation?.customerId ?? state.selectedCustomerId,
  }
}

function updateRoute(updates: RouteUpdate) {
  if (typeof window === 'undefined') return
  const url = new URL(window.location.href)
  Object.entries(updates).forEach(([key, value]) => {
    if (value === null) {
      url.searchParams.delete(key)
      return
    }
    if (value !== undefined) {
      url.searchParams.set(key, value)
    }
  })

  const next = `${url.pathname}${url.search}${url.hash}`
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`
  if (next !== current) {
    window.history.pushState({}, '', next)
  }
}

async function getDb() {
  return openDB<TicketDeskDb>(dbName, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('state')) {
        db.createObjectStore('state')
      }
    },
  })
}

async function readState() {
  const db = await getDb()
  return db.get('state', stateKey)
}

async function writeState(state: OmniState) {
  const db = await getDb()
  await db.put('state', state, stateKey)
}

function mergeReferenceData(state: OmniState): OmniState {
  return {
    ...state,
    settings: state.settings ?? initialOmniState.settings,
    epics: initialOmniState.epics,
    backlog: initialOmniState.backlog,
    issues: initialOmniState.issues,
  }
}

const seedChannelById = new Map(initialOmniState.channels.map((channel) => [channel.id, channel]))

function normalizeChannelId(value: string): ChannelId {
  if (value === 'voice') return 'phone'
  return value as ChannelId
}

function backendChannelId(value: ChannelId): string {
  return value === 'phone' ? 'voice' : value
}

function mapPriority(value: BackendTicket['priority']): Priority {
  if (value === 'normal') return 'medium'
  return value
}

function backendPriority(value: Priority): BackendTicket['priority'] {
  if (value === 'medium') return 'normal'
  return value
}

function mapStatus(value: BackendTicket['status']): ConversationStatus {
  if (value === 'solved' || value === 'closed') return 'resolved'
  return value
}

function backendStatus(value: ConversationStatus): BackendTicket['status'] {
  if (value === 'new' || value === 'open') return 'open'
  if (value === 'resolved') return 'solved'
  return value
}

function mapSentiment(value: BackendTicket['sentiment'] | BackendCustomer['sentiment']): Sentiment {
  if (value === 'angry') return 'at-risk'
  return value
}

function mapSlaState(ticket: BackendTicket): SlaState {
  if (ticket.sla.breached || ticket.sla.risk === 'breached') return 'breached'
  if (ticket.sla.risk === 'at_risk') return 'risk'
  return 'healthy'
}

function mapTimelineType(event: BackendTimelineEvent): TimelineType {
  if (event.type === 'public_reply') return 'agent-reply'
  if (event.type === 'internal_note') return 'internal-note'
  if (event.type.startsWith('handoff_')) return 'handoff'
  if (event.type === 'connector_receipt' || event.type === 'status_change' || event.type === 'ai_decision') {
    return 'automation'
  }
  const channelId = normalizeChannelId(event.channel)
  if (channelId === 'phone') return 'voice-log'
  if (channelId === 'portal') return 'portal-comment'
  if (channelId === 'api') return 'api-event'
  if (channelId === 'instagram' || channelId === 'facebook') return 'social-dm'
  if (channelId === 'chat' || channelId === 'whatsapp' || channelId === 'sms') return 'chat-transcript'
  return 'customer-message'
}

function mapTimelineAuthorRole(event: BackendTimelineEvent): TimelineEvent['authorRole'] {
  if (event.type === 'public_reply') return 'agent'
  if (event.type === 'inbound') return 'customer'
  if (event.actor === 'api' || event.actor === 'AI Work Queue') return 'system'
  return event.public ? 'agent' : 'system'
}

function mapDeliveryState(value: unknown): TimelineEvent['deliveryState'] {
  if (
    value === 'queued' ||
    value === 'sending' ||
    value === 'sent' ||
    value === 'failed' ||
    value === 'retrying' ||
    value === 'dead_lettered'
  ) {
    return value
  }
  return undefined
}

function initials(value: string) {
  return value
    .split(' ')
    .map((part) => part[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function formatAccountValue(value: number) {
  if (!value) return '$0'
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}k`
  return `$${value}`
}

function mapContactMethods(customer: BackendCustomer): CustomerProfile['contactMethods'] {
  const methods: CustomerProfile['contactMethods'] = customer.contact_points.map((point) => {
    const channelId = normalizeChannelId(point.channel)
    return {
      type:
        channelId === 'email'
          ? 'email'
          : channelId === 'phone'
            ? 'phone'
            : channelId === 'whatsapp'
              ? 'whatsapp'
              : channelId === 'sms'
                ? 'sms'
                : channelId === 'portal'
                  ? 'portal'
                  : 'social',
      label: channelId === 'facebook' ? 'Facebook' : channelId === 'instagram' ? 'Instagram' : channelId,
      value: point.value,
      primary: false,
    }
  })

  if (!methods.some((method) => method.type === 'email')) {
    methods.unshift({
      type: 'email',
      label: 'Email',
      value: customer.email,
      primary: true,
    })
  } else {
    methods[0] = { ...methods[0], primary: true }
  }

  return methods
}

function mapChannel(channel: BackendChannel): Channel {
  const channelId = normalizeChannelId(channel.type)
  const seed = seedChannelById.get(channelId)
  const healthScore = channel.health === 'healthy' ? 92 : channel.health === 'degraded' ? 68 : 42
  return {
    id: channelId,
    label: seed?.label ?? channel.name,
    shortLabel: seed?.shortLabel ?? channel.name.slice(0, 10),
    status: channel.health,
    queueDepth: channel.queued,
    activeSessions: channel.active,
    avgWaitMinutes: seed?.avgWaitMinutes ?? Math.max(5, channel.queued * 2),
    targetMinutes: seed?.targetMinutes ?? 30,
    slaRisk: channel.sla_risk,
    health: Math.max(12, healthScore - channel.sla_risk * 3),
    intakeEnabled: channel.health !== 'paused',
    description: seed?.description ?? channel.capabilities.join(', '),
  }
}

function mapAgent(agent: BackendAgent, ticketContexts: BackendTicketContext[]): AgentProfile {
  const assignedTickets = ticketContexts.filter((context) => context.ticket.assignee_id === agent.id)
  return {
    id: agent.id,
    name: agent.name,
    role: agent.team,
    avatar: initials(agent.name),
    availability: agent.status,
    skills: agent.skills.map((skill) => normalizeChannelId(skill).replace('-', ' ')),
    load: assignedTickets.length,
    capacity: agent.capacity,
    occupancy: agent.occupancy,
    csat: Math.max(82, 100 - agent.occupancy / 2),
    shift: `${agent.languages.join(', ').toUpperCase()} coverage`,
  }
}

function mapCustomer(
  customer: BackendCustomer,
  companiesById: Map<string, BackendCompany>,
  ticketContexts: BackendTicketContext[],
): CustomerProfile {
  const company = customer.company_id ? companiesById.get(customer.company_id) : undefined
  const customerTickets = ticketContexts.filter((context) => context.ticket.customer_id === customer.id)
  const latestTicket = customerTickets
    .slice()
    .sort((a, b) => b.ticket.updated_at.localeCompare(a.ticket.updated_at))[0]
  const primaryPhoneMethod = customer.contact_points.find((point) => {
    const channelId = normalizeChannelId(point.channel)
    return channelId === 'phone' || channelId === 'whatsapp' || channelId === 'sms'
  })

  return {
    id: customer.id,
    name: customer.name,
    company: company?.name ?? 'Independent customer',
    title: company ? `${company.tier} account` : 'Customer',
    email: customer.email,
    phone: primaryPhoneMethod?.value ?? '',
    location: customer.location || 'Market workspace',
    healthScore: company?.health_score ?? 72,
    csat: customer.sentiment === 'positive' ? 4.7 : customer.sentiment === 'neutral' ? 4.1 : 3.4,
    totalConversations: customerTickets.length,
    openValue: formatAccountValue(company?.account_value ?? 0),
    preferredChannels: customer.preferred_channels.map((channel) => normalizeChannelId(channel)),
    contactMethods: mapContactMethods(customer),
    tags: customer.tags,
    recentActivity: latestTicket
      ? latestTicket.ticket.subject
      : customer.notes || 'No recent backend ticket activity yet.',
  }
}

function buildCopilot(context: BackendTicketContext, settings: WorkspaceSettings) {
  const latestDecision = context.ai_decisions
    .slice()
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
  return {
    summary: context.ticket.ai_summary || latestDecision?.summary || 'Backend snapshot is ready for review.',
    intent: context.ticket.tags[0] ?? 'Operational support',
    sentiment: mapSentiment(context.ticket.sentiment),
    autoTags: context.ticket.tags,
    slaReason:
      mapSlaState(context.ticket) === 'breached'
        ? 'Backend SLA state is breached and needs supervisor attention.'
        : mapSlaState(context.ticket) === 'risk'
          ? 'Backend SLA state is at risk and should be handled next.'
          : 'Backend SLA state is on track.',
    suggestedReply:
      context.ticket.recommended_action ||
      'Acknowledge the customer, confirm ownership, and set the next update time.',
    suggestedArticle: context.company?.name
      ? `Resolution guidance for ${context.company.name}`
      : 'Customer response checklist',
    escalation:
      settings.aiWorkQueueAutomationEnabled && latestDecision
        ? `AI queue decision ${latestDecision.decision_type} is active.`
        : 'Manual supervisor review required before escalation.',
    recommendedAction:
      context.ticket.recommended_action ||
      'Review the backend ticket context and confirm the next action.',
    confidence: Math.round((latestDecision?.confidence ?? 0.72) * 100),
  }
}

function mapConversation(
  context: BackendTicketContext,
  settings: WorkspaceSettings,
): OmniConversation {
  const outboundByTimelineId = new Map(
    context.outbound_messages
      .filter((message) => message.timeline_event_id)
      .map((message) => [message.timeline_event_id, message.status]),
  )
  const timeline = context.timeline.map((event) => ({
    id: event.id,
    type: mapTimelineType(event),
    channelId: normalizeChannelId(event.channel),
    author: event.actor,
    authorRole: mapTimelineAuthorRole(event),
    timestamp: event.created_at,
    body: event.body,
    deliveryState:
      mapDeliveryState(outboundByTimelineId.get(event.id)) ??
      mapDeliveryState(event.metadata.delivery_status),
  }))
  const latestTimeline = timeline[timeline.length - 1]
  return {
    id: context.ticket.id,
    ticketNumber: context.ticket.public_id,
    customerId: context.ticket.customer_id,
    channelId: normalizeChannelId(context.ticket.channel),
    subject: context.ticket.subject,
    preview: latestTimeline?.body ?? context.ticket.description,
    status: mapStatus(context.ticket.status),
    priority: mapPriority(context.ticket.priority),
    sentiment: mapSentiment(context.ticket.sentiment),
    intent: context.ticket.tags[0] ?? 'Operational support',
    group: context.ticket.team,
    assigneeId: context.ticket.assignee_id ?? '',
    createdAt: context.ticket.created_at,
    updatedAt: context.ticket.updated_at,
    firstResponseDue: context.ticket.sla.first_response_due_at,
    resolutionDue: context.ticket.sla.resolution_due_at,
    slaState: mapSlaState(context.ticket),
    language: 'English',
    unread: latestTimeline?.authorRole === 'customer',
    tags: context.ticket.tags,
    tasks:
      context.ticket.tasks.length > 0
        ? context.ticket.tasks.map((task) => ({
            id: task.id,
            label: task.label,
            done: task.complete,
          }))
        : [
            {
              id: `${context.ticket.id}-task-review`,
              label: 'Review backend recommendation and confirm next action',
              done: false,
            },
          ],
    timeline,
    copilot: buildCopilot(context, settings),
  }
}

function mapHandoff(
  handoff: BackendHandoff,
  conversationsById: Map<string, OmniConversation>,
): OmniState['handoffs'][number] {
  const conversation = conversationsById.get(handoff.ticket_id)
  return {
    id: handoff.id,
    conversationId: handoff.ticket_id,
    ticketNumber: conversation?.ticketNumber ?? handoff.ticket_id,
    customerId: conversation?.customerId ?? '',
    sourceTeam: handoff.from_team,
    receivingTeam: handoff.to_team,
    requesterId: handoff.requested_by,
    ownerId: conversation?.assigneeId ?? '',
    reason: handoff.reason,
    context: conversation?.preview ?? handoff.reason,
    customerImpact: conversation?.copilot.summary ?? 'Customer-facing impact needs confirmation.',
    acceptanceCriteria: 'Receiving team confirms ownership and returns a customer-ready update.',
    status:
      handoff.status === 'resolved'
        ? 'completed'
        : handoff.status === 'cancelled'
          ? 'blocked'
          : handoff.status === 'accepted'
            ? 'accepted'
            : handoff.status,
    priority: conversation?.priority ?? 'medium',
    dueAt: handoff.due_at,
    createdAt: handoff.created_at,
    updatedAt: handoff.updated_at,
    checklist: handoff.checklist.map((task) => ({
      id: task.id,
      label: task.label,
      done: task.complete,
    })),
    blockers: handoff.blocker ? [handoff.blocker] : [],
  }
}

function mapKnowledgeArticle(article: BackendKnowledgeArticle): KnowledgeArticle {
  return {
    id: article.id,
    title: article.title,
    category: article.tags[0] ?? 'Operations',
    status: article.status === 'published' ? 'published' : article.status === 'draft' ? 'draft' : 'review',
    language: article.language,
    helpfulness: 89,
    deflection: 34,
    ownerId: 'backend',
    intents: article.tags,
    updatedAt: article.updated_at,
  }
}

function mapRule(rule: BackendAutomationRule): OmniState['rules'][number] {
  const status: RuleStatus = rule.enabled ? 'active' : 'paused'
  return {
    id: rule.id,
    name: rule.name,
    trigger: rule.trigger,
    condition: 'Backend-managed rule',
    action: rule.action,
    owner: 'Backend automation',
    status,
    health: Math.max(30, 100 - rule.failure_count * 12),
    lastFired: rule.last_fired_at ?? new Date().toISOString(),
    failures: rule.failure_count,
  }
}

function mergeBackendSnapshot(current: OmniState, snapshot: BackendSnapshot): OmniState {
  const settings = {
    ...current.settings,
    aiWorkQueueAutomationEnabled: snapshot.settings.ai_work_queue_automation_enabled,
  }
  const channels = snapshot.channels.map(mapChannel)
  const conversations = snapshot.tickets.map((context) => mapConversation(context, settings))
  const conversationsById = new Map(conversations.map((conversation) => [conversation.id, conversation]))
  const companiesById = new Map(snapshot.companies.map((company) => [company.id, company]))
  const customers = snapshot.customers.map((customer) => mapCustomer(customer, companiesById, snapshot.tickets))
  const agents = snapshot.agents.map((agent) => mapAgent(agent, snapshot.tickets))
  const handoffs = snapshot.handoffs.map((handoff) => mapHandoff(handoff, conversationsById))
  const selectedConversationId =
    conversations.find((conversation) => conversation.id === current.selectedConversationId)?.id ??
    conversations[0]?.id ??
    ''
  const selectedCustomerId =
    customers.find((customer) => customer.id === current.selectedCustomerId)?.id ??
    conversationsById.get(selectedConversationId)?.customerId ??
    customers[0]?.id ??
    ''
  const selectedChannelId =
    current.selectedChannelId === 'all' || channels.some((channel) => channel.id === current.selectedChannelId)
      ? current.selectedChannelId
      : 'all'
  const nextFilters = {
    ...current.filters,
    assignee:
      current.filters.assignee === 'all' || agents.some((agent) => agent.id === current.filters.assignee)
        ? current.filters.assignee
        : 'all',
    channel:
      current.filters.channel === 'all' || channels.some((channel) => channel.id === current.filters.channel)
        ? current.filters.channel
        : 'all',
  }

  return routeStateFromUrl({
    ...current,
    channels,
    conversations,
    customers,
    agents,
    articles: snapshot.knowledge.map(mapKnowledgeArticle),
    rules: snapshot.rules.map(mapRule),
    handoffs,
    selectedConversationId,
    selectedCustomerId,
    selectedChannelId,
    filters: nextFilters,
    settings,
  })
}

function uid(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.round(Math.random() * 1000)}`
}

function eventTypeForMode(mode: ComposerInput['mode']): TimelineEvent['type'] {
  if (mode === 'note') return 'internal-note'
  if (mode === 'handoff') return 'handoff'
  return 'agent-reply'
}

function nextStatusForMode(mode: ComposerInput['mode'], current: ConversationStatus) {
  if (mode === 'reply') return 'pending'
  if (mode === 'handoff') return 'waiting'
  return current
}

function dueInMinutes(minutes: number) {
  return new Date(Date.now() + minutes * 60 * 1000).toISOString()
}

function nextTicketNumber(conversations: OmniConversation[]) {
  const max = conversations.reduce((highest, conversation) => {
    const match = conversation.ticketNumber.match(/OMNI-(\d+)/)
    return match ? Math.max(highest, Number(match[1])) : highest
  }, 1000)
  return `OMNI-${max + 1}`
}

function automatedAssigneeId(state: OmniState, input: NewTicketInput) {
  const channel = state.channels.find((item) => item.id === input.channelId)
  const channelNeedles: Record<string, string[]> = {
    email: ['email', 'billing'],
    chat: ['chat'],
    phone: ['phone', 'voice'],
    whatsapp: ['whatsapp', 'chat'],
    sms: ['sms', 'chat'],
    instagram: ['instagram', 'social'],
    facebook: ['facebook', 'social'],
    portal: ['portal'],
    api: ['partner', 'api', 'engineering'],
    internal: ['internal', 'handoff'],
  }
  const needles = [
    ...(channelNeedles[input.channelId] ?? []),
    channel?.label ?? '',
    input.group,
  ].map((value) => value.toLowerCase())

  const rankedAgents = [...state.agents]
    .filter((agent) => agent.availability !== 'offline')
    .map((agent) => {
      const haystack = `${agent.role} ${agent.skills.join(' ')}`.toLowerCase()
      const skillMatch = needles.some((needle) => needle && haystack.includes(needle))
      const availabilityBoost = agent.availability === 'available' ? 24 : agent.availability === 'busy' ? 4 : 0
      const loadRoom = Math.max(agent.capacity - agent.load, 0) * 6
      const occupancyRoom = Math.max(100 - agent.occupancy, 0)
      return {
        agent,
        score: (skillMatch ? 80 : 0) + availabilityBoost + loadRoom + occupancyRoom + agent.csat / 5,
      }
    })
    .sort((a, b) => b.score - a.score)

  return rankedAgents[0]?.agent.id ?? input.assigneeId
}

function matchesSearch(conversation: OmniConversation, search: string) {
  if (!search.trim()) return true
  const haystack = [
    conversation.ticketNumber,
    conversation.subject,
    conversation.preview,
    conversation.intent,
    conversation.group,
    conversation.tags.join(' '),
  ]
    .join(' ')
    .toLowerCase()
  return haystack.includes(search.trim().toLowerCase())
}

function filterConversation(conversation: OmniConversation, filters: InboxFilters) {
  return (
    (filters.channel === 'all' || conversation.channelId === filters.channel) &&
    (filters.status === 'all' || conversation.status === filters.status) &&
    (filters.priority === 'all' || conversation.priority === filters.priority) &&
    (filters.sla === 'all' || conversation.slaState === filters.sla) &&
    (filters.assignee === 'all' || conversation.assigneeId === filters.assignee) &&
    (filters.sentiment === 'all' || conversation.sentiment === filters.sentiment) &&
    matchesSearch(conversation, filters.search)
  )
}

export function useOmniStore() {
  const [state, setState] = useState<OmniState>(initialOmniState)
  const [backendSession, setBackendSession] = useState<BackendSession | null>(() => {
    if (typeof window === 'undefined') return null
    const stored = window.localStorage.getItem(backendSessionKey)
    if (!stored) return null
    try {
      return JSON.parse(stored) as BackendSession
    } catch {
      window.localStorage.removeItem(backendSessionKey)
      return null
    }
  })
  const [hydrated, setHydrated] = useState(false)
  const [online, setOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine,
  )
  const [backendSync, setBackendSync] = useState<BackendSyncState>({
    status: 'idle',
    baseUrl: getBackendBaseUrl(),
  })

  useEffect(() => {
    let cancelled = false
    readState()
      .then((stored) => {
        if (!cancelled) {
          const nextState =
            stored?.version === initialOmniState.version
              ? mergeReferenceData(stored)
              : initialOmniState
          setState(routeStateFromUrl(nextState))
        }
      })
      .finally(() => {
        if (!cancelled) setHydrated(true)
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!hydrated) return
    const timer = window.setTimeout(() => {
      writeState(state).catch(() => undefined)
    }, 150)
    return () => window.clearTimeout(timer)
  }, [hydrated, state])

  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])

  useEffect(() => {
    const onPopState = () => {
      patchState((current) => routeStateFromUrl(current))
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  function applyBackendSettings(aiWorkQueueAutomationEnabled: boolean) {
    patchState((current) => ({
      ...current,
      settings: {
        ...current.settings,
        aiWorkQueueAutomationEnabled,
      },
    }))
  }

  function saveBackendSession(session: BackendSession | null) {
    setBackendSession(session)
    if (typeof window === 'undefined') return
    if (session) {
      window.localStorage.setItem(backendSessionKey, JSON.stringify(session))
    } else {
      window.localStorage.removeItem(backendSessionKey)
    }
  }

  async function login(input: BackendLoginInput) {
    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))
    try {
      const session = await loginBackend(input)
      saveBackendSession(session)
      const snapshot = await fetchBackendSnapshot(session)
      patchState((current) => mergeBackendSnapshot(current, snapshot))
      setBackendSync({
        status: 'connected',
        baseUrl: getBackendBaseUrl(),
        lastSyncAt: new Date().toISOString(),
        snapshot,
      })
    } catch (error) {
      saveBackendSession(null)
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'Login failed',
      }))
    }
  }

  function logout() {
    saveBackendSession(null)
    setBackendSync({
      status: 'idle',
      baseUrl: getBackendBaseUrl(),
    })
  }

  async function switchMarket(marketId: string) {
    if (!backendSession) return
    await login({
      email: backendSession.user.email,
      password: 'omni-demo',
      market_id: marketId,
    })
  }

  async function refreshBackend() {
    if (!backendSession) {
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: 'Sign in to sync market-scoped backend data.',
      }))
      return
    }
    if (!online) {
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: 'Browser is offline. Backend sync resumes when connectivity returns.',
      }))
      return
    }

    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))

    try {
      const snapshot = await fetchBackendSnapshot(backendSession)
      patchState((current) => mergeBackendSnapshot(current, snapshot))
      setBackendSync({
        status: 'connected',
        baseUrl: getBackendBaseUrl(),
        lastSyncAt: new Date().toISOString(),
        snapshot,
      })
    } catch (error) {
      if (error instanceof Error && error.message.startsWith('401')) {
        saveBackendSession(null)
      }
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'Backend sync failed',
      }))
    }
  }

  useEffect(() => {
    if (!hydrated || !online || !backendSession) return
    let cancelled = false

    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))

    fetchBackendSnapshot(backendSession)
      .then((snapshot) => {
        if (cancelled) return
        patchState((current) => mergeBackendSnapshot(current, snapshot))
        setBackendSync({
          status: 'connected',
          baseUrl: getBackendBaseUrl(),
          lastSyncAt: new Date().toISOString(),
          snapshot,
        })
      })
      .catch((error) => {
        if (cancelled) return
        if (error instanceof Error && error.message.startsWith('401')) {
          saveBackendSession(null)
        }
        setBackendSync((current) => ({
          ...current,
          status: 'error',
          error: error instanceof Error ? error.message : 'Backend sync failed',
        }))
      })

    return () => {
      cancelled = true
    }
  }, [backendSession, hydrated, online])

  const selectedConversation =
    state.conversations.find((conversation) => conversation.id === state.selectedConversationId) ??
    state.conversations[0]

  const selectedCustomer =
    state.customers.find((customer) => customer.id === state.selectedCustomerId) ??
    state.customers.find((customer) => customer.id === selectedConversation?.customerId) ??
    state.customers[0]

  const filteredConversations = useMemo(() => {
    return state.conversations
      .filter((conversation) => filterConversation(conversation, state.filters))
      .sort((a, b) => {
        const priorityScore: Record<Priority, number> = { urgent: 4, high: 3, medium: 2, low: 1 }
        const slaScore: Record<SlaState, number> = { breached: 4, risk: 3, healthy: 2, paused: 1 }
        return (
          slaScore[b.slaState] - slaScore[a.slaState] ||
          priorityScore[b.priority] - priorityScore[a.priority] ||
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        )
      })
  }, [state.conversations, state.filters])

  const metrics = useMemo(() => {
    const open = state.conversations.filter((conversation) => conversation.status !== 'resolved')
    const atRisk = open.filter(
      (conversation) => conversation.slaState === 'risk' || conversation.slaState === 'breached',
    )
    const breached = open.filter((conversation) => conversation.slaState === 'breached')
    const activeChannels = state.channels.filter((channel) => channel.intakeEnabled).length
    const avgHealth = Math.round(
      state.channels.reduce((total, channel) => total + channel.health, 0) / state.channels.length,
    )
    const avgOccupancy = Math.round(
      state.agents.reduce((total, agent) => total + agent.occupancy, 0) / state.agents.length,
    )
    const csat = (
      state.agents.reduce((total, agent) => total + agent.csat, 0) / state.agents.length
    ).toFixed(1)

    return {
      open: open.length,
      atRisk: atRisk.length,
      breached: breached.length,
      activeChannels,
      avgHealth,
      avgOccupancy,
      csat,
      outbox: state.outbox.length,
    }
  }, [state])

  function patchState(updater: (current: OmniState) => OmniState) {
    setState((current) => updater(current))
  }

  function commitBackendSnapshot(
    snapshot: BackendSnapshot,
    selection?: {
      screen?: ScreenId
      conversationId?: string
      customerId?: string
      channelId?: ChannelId | 'all'
    },
  ) {
    if (selection) {
      updateRoute({
        screen: selection.screen,
        conversation: selection.conversationId,
        customer: selection.customerId,
        channel: selection.channelId === 'all' ? null : selection.channelId,
      })
    }

    patchState((current) => {
      const merged = mergeBackendSnapshot(current, snapshot)
      if (!selection) return merged
      return routeStateFromUrl({
        ...merged,
        selectedScreen: selection.screen ?? merged.selectedScreen,
        selectedConversationId: selection.conversationId ?? merged.selectedConversationId,
        selectedCustomerId: selection.customerId ?? merged.selectedCustomerId,
        selectedChannelId: selection.channelId ?? merged.selectedChannelId,
        filters: selection.channelId ? { ...merged.filters, channel: selection.channelId } : merged.filters,
      })
    })

    setBackendSync({
      status: 'connected',
      baseUrl: getBackendBaseUrl(),
      lastSyncAt: new Date().toISOString(),
      snapshot,
    })
  }

  function syncBackendMutation<T>(
    operation: (session: BackendSession) => Promise<T>,
    selection?: (result: T) => {
      screen?: ScreenId
      conversationId?: string
      customerId?: string
      channelId?: ChannelId | 'all'
    },
  ) {
    if (!online || !backendSession) return false
    const session = backendSession

    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))

    void operation(session)
      .then(async (result) => {
        const snapshot = await fetchBackendSnapshot(session)
        commitBackendSnapshot(snapshot, selection?.(result))
      })
      .catch((error) => {
        if (error instanceof Error && error.message.startsWith('401')) {
          saveBackendSession(null)
        }
        setBackendSync((current) => ({
          ...current,
          status: 'error',
          error: error instanceof Error ? error.message : 'Backend write failed',
        }))
      })

    return true
  }

  function selectScreen(screen: ScreenId) {
    updateRoute({ screen })
    patchState((current) => ({ ...current, selectedScreen: screen }))
  }

  function selectConversation(conversationId: string) {
    const conversation = state.conversations.find((item) => item.id === conversationId)
    const targetScreen = state.selectedScreen === 'command' ? 'inbox' : state.selectedScreen
    updateRoute({
      screen: targetScreen,
      conversation: conversationId,
      customer: conversation?.customerId,
    })
    patchState((current) => {
      const conversation = current.conversations.find((item) => item.id === conversationId)
      return {
        ...current,
        selectedConversationId: conversationId,
        selectedCustomerId: conversation?.customerId ?? current.selectedCustomerId,
        selectedScreen: current.selectedScreen === 'command' ? 'inbox' : current.selectedScreen,
      }
    })
  }

  function selectCustomer(customerId: string) {
    const targetScreen = state.selectedScreen === 'command' ? 'customers' : state.selectedScreen
    updateRoute({ screen: targetScreen, customer: customerId })
    patchState((current) => ({
      ...current,
      selectedCustomerId: customerId,
      selectedScreen: current.selectedScreen === 'command' ? 'customers' : current.selectedScreen,
    }))
  }

  function setFilters(filters: Partial<InboxFilters>) {
    patchState((current) => ({
      ...current,
      filters: { ...current.filters, ...filters },
    }))
  }

  function resetFilters() {
    patchState((current) => ({
      ...current,
      filters: initialOmniState.filters,
    }))
  }

  function setSelectedChannel(channelId: ChannelId | 'all') {
    updateRoute({ screen: 'channels', channel: channelId === 'all' ? null : channelId })
    patchState((current) => ({
      ...current,
      selectedChannelId: channelId,
      filters: { ...current.filters, channel: channelId },
      selectedScreen: 'channels',
    }))
  }

  function submitComposer(input: ComposerInput) {
    if (!input.body.trim()) return

    if (input.mode === 'handoff') {
      if (
        syncBackendMutation(
          (session) =>
            createBackendHandoff(
              input.conversationId,
              {
                to_team: input.handoffTeam || 'Operations',
                requested_by: session.user.id,
                reason: input.handoffReason || 'Operational support required',
                due_minutes: 60,
                checklist: [
                  'Accept ownership and confirm receiving owner',
                  'Review customer impact and internal context',
                  'Return customer-ready next action',
                ],
              },
              session,
            ),
          () => {
            const conversation = state.conversations.find((item) => item.id === input.conversationId)
            return {
              screen: state.selectedScreen,
              conversationId: input.conversationId,
              customerId: conversation?.customerId,
              channelId: input.channelId,
            }
          },
        )
      ) {
        return
      }
    } else if (
      syncBackendMutation(
        (session) =>
          postBackendReply(
            input.conversationId,
            {
              channel: backendChannelId(input.channelId),
              actor: session.user.name,
              body: input.body.trim(),
              public: input.mode === 'reply',
            },
            session,
          ),
        () => {
          const conversation = state.conversations.find((item) => item.id === input.conversationId)
          return {
            screen: state.selectedScreen,
            conversationId: input.conversationId,
            customerId: conversation?.customerId,
            channelId: input.channelId,
          }
        },
      )
    ) {
      return
    }

    const createdAt = new Date().toISOString()
    const event: TimelineEvent = {
      id: uid('event'),
      type: eventTypeForMode(input.mode),
      channelId: input.channelId,
      author: input.mode === 'handoff' ? 'Operations handoff' : 'You',
      authorRole: input.mode === 'handoff' ? 'system' : 'agent',
      timestamp: createdAt,
      body: input.body.trim(),
      deliveryState: input.online ? 'sent' : 'queued',
    }

    patchState((current) => {
      const conversation = current.conversations.find((item) => item.id === input.conversationId)
      const handoffTeam = input.handoffTeam || 'Operations'
      const owner =
        current.agents.find((agent) =>
          agent.skills.some((skill) => handoffTeam.toLowerCase().includes(skill.toLowerCase())),
        ) ?? current.agents.find((agent) => agent.id === conversation?.assigneeId) ?? current.agents[0]
      const handoff =
        input.mode === 'handoff' && conversation
          ? {
              id: uid('HO'),
              conversationId: conversation.id,
              ticketNumber: conversation.ticketNumber,
              customerId: conversation.customerId,
              sourceTeam: conversation.group,
              receivingTeam: handoffTeam,
              requesterId: conversation.assigneeId,
              ownerId: owner.id,
              reason: input.handoffReason || 'Operational support required',
              context: input.body.trim(),
              customerImpact: conversation.preview,
              acceptanceCriteria: 'Receiving team accepts ownership, confirms next action, and returns a customer-ready update.',
              status: 'requested' as const,
              priority: conversation.priority,
              dueAt: dueInMinutes(conversation.priority === 'urgent' ? 45 : 120),
              createdAt,
              updatedAt: createdAt,
              checklist: [
                { id: uid('step'), label: 'Accept ownership and confirm receiving owner', done: false },
                { id: uid('step'), label: 'Review customer impact and internal context', done: false },
                { id: uid('step'), label: 'Return customer-ready next action', done: false },
              ],
              blockers: [],
            }
          : undefined

      return {
        ...current,
        handoffs: handoff ? [handoff, ...current.handoffs] : current.handoffs,
        outbox: input.online
          ? current.outbox
          : [
              ...current.outbox,
              {
                id: uid('outbox'),
                conversationId: input.conversationId,
                channelId: input.channelId,
                mode: input.mode,
                body: input.body.trim(),
                createdAt,
                state: 'queued',
              },
            ],
        conversations: current.conversations.map((item) =>
          item.id === input.conversationId
            ? {
                ...item,
                status: nextStatusForMode(input.mode, item.status),
                channelId: input.channelId,
                updatedAt: createdAt,
                unread: false,
                timeline: [...item.timeline, event],
              }
            : item,
        ),
      }
    })
  }

  function createConversation(input: NewTicketInput) {
    if (
      syncBackendMutation(
        (session) =>
          createBackendTicket(
            {
              subject: input.subject.trim(),
              description: input.body.trim(),
              customer_id: input.customerId,
              channel: backendChannelId(input.channelId),
              priority: backendPriority(input.priority),
              tags: ['new-request'],
            },
            session,
          ),
        (ticket) => ({
          screen: 'inbox',
          conversationId: ticket.id,
          customerId: ticket.customer_id,
          channelId: normalizeChannelId(ticket.channel),
        }),
      )
    ) {
      return
    }

    const createdAt = new Date().toISOString()
    patchState((current) => {
      const customer = current.customers.find((item) => item.id === input.customerId) ?? current.customers[0]
      const ticketNumber = nextTicketNumber(current.conversations)
      const conversationId = uid('conv')
      const aiAutomationEnabled = current.settings?.aiWorkQueueAutomationEnabled ?? true
      const assigneeId = aiAutomationEnabled ? automatedAssigneeId(current, input) : input.assigneeId
      const conversation: OmniConversation = {
        id: conversationId,
        ticketNumber,
        customerId: customer.id,
        channelId: input.channelId,
        subject: input.subject.trim(),
        preview: input.body.trim(),
        status: 'new',
        priority: input.priority,
        sentiment: 'neutral',
        intent: 'New customer request',
        group: input.group,
        assigneeId,
        createdAt,
        updatedAt: createdAt,
        firstResponseDue: dueInMinutes(input.priority === 'urgent' ? 15 : 45),
        resolutionDue: dueInMinutes(input.priority === 'urgent' ? 240 : 1440),
        slaState: 'healthy',
        language: 'English',
        unread: true,
        tags: aiAutomationEnabled ? ['new-request', 'ai-routed'] : ['new-request'],
        tasks: [
          {
            id: uid('task'),
            label: aiAutomationEnabled
              ? 'Review AI triage and confirm next update time'
              : 'Confirm customer request and next update time',
            done: false,
          },
          {
            id: uid('task'),
            label: aiAutomationEnabled
              ? 'Validate automated owner and response path'
              : 'Assign owner and choose response path',
            done: false,
          },
        ],
        timeline: [
          {
            id: uid('event'),
            type: 'customer-message',
            channelId: input.channelId,
            author: customer.name,
            authorRole: 'customer',
            timestamp: createdAt,
            body: input.body.trim(),
          },
        ],
        copilot: {
          summary: 'New customer request is ready for triage. Confirm the issue, owner, and next update time.',
          intent: 'New customer request',
          sentiment: 'neutral',
          autoTags: ['new-request', input.channelId],
          slaReason: 'First response promise is on track.',
          suggestedReply:
            'Thanks for contacting us. I have opened this request and will confirm the next action and update time shortly.',
          suggestedArticle: 'Customer request intake checklist',
          escalation: 'No escalation needed yet.',
          recommendedAction: aiAutomationEnabled
            ? 'Acknowledge the customer; AI has routed the ticket to the best available owner.'
            : 'Acknowledge the customer and assign the correct owner.',
          confidence: 74,
        },
      }

      updateRoute({
        screen: 'inbox',
        channel: input.channelId,
        conversation: conversationId,
        customer: customer.id,
      })

      return {
        ...current,
        selectedScreen: 'inbox',
        selectedConversationId: conversationId,
        selectedCustomerId: customer.id,
        selectedChannelId: input.channelId,
        filters: { ...initialOmniState.filters, channel: input.channelId },
        conversations: [conversation, ...current.conversations],
        channels: current.channels.map((channel) =>
          channel.id === input.channelId
            ? {
                ...channel,
                queueDepth: channel.queueDepth + 1,
                activeSessions: channel.activeSessions + 1,
              }
            : channel,
        ),
      }
    })
  }

  function updateConversation(conversationId: string, patch: Partial<OmniConversation>) {
    const backendPatch: {
      status?: BackendTicket['status']
      priority?: BackendTicket['priority']
      assignee_id?: string | null
    } = {}

    if (patch.status) backendPatch.status = backendStatus(patch.status)
    if (patch.priority) backendPatch.priority = backendPriority(patch.priority)
    if ('assigneeId' in patch) backendPatch.assignee_id = patch.assigneeId || null

    if (
      Object.keys(backendPatch).length > 0 &&
      syncBackendMutation(
        (session) => patchBackendTicket(conversationId, backendPatch, session),
        () => {
          const conversation = state.conversations.find((item) => item.id === conversationId)
          return {
            screen: state.selectedScreen,
            conversationId,
            customerId: conversation?.customerId,
            channelId: conversation?.channelId,
          }
        },
      )
    ) {
      return
    }

    patchState((current) => ({
      ...current,
      conversations: current.conversations.map((conversation) =>
        conversation.id === conversationId
          ? { ...conversation, ...patch, updatedAt: new Date().toISOString() }
          : conversation,
      ),
    }))
  }

  function updateSettings(patch: Partial<WorkspaceSettings>) {
    patchState((current) => ({
      ...current,
      settings: {
        ...initialOmniState.settings,
        ...current.settings,
        ...patch,
      },
    }))

    if (!online || !backendSession || patch.aiWorkQueueAutomationEnabled === undefined) return

    patchBackendSettings({
      ai_work_queue_automation_enabled: patch.aiWorkQueueAutomationEnabled,
    }, backendSession)
      .then((settings) => {
        applyBackendSettings(settings.ai_work_queue_automation_enabled)
        setBackendSync((current) => ({
          ...current,
          status: 'connected',
          lastSyncAt: new Date().toISOString(),
          snapshot: current.snapshot
            ? {
                ...current.snapshot,
                settings,
              }
            : current.snapshot,
          error: undefined,
        }))
      })
      .catch((error) => {
        setBackendSync((current) => ({
          ...current,
          status: 'error',
          error: error instanceof Error ? error.message : 'Backend settings update failed',
        }))
      })
  }

  function toggleTask(conversationId: string, taskId: string) {
    patchState((current) => ({
      ...current,
      conversations: current.conversations.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              tasks: conversation.tasks.map((task) =>
                task.id === taskId ? { ...task, done: !task.done } : task,
              ),
              updatedAt: new Date().toISOString(),
            }
          : conversation,
      ),
    }))
  }

  function toggleChannelIntake(channelId: ChannelId) {
    const channel = state.channels.find((item) => item.id === channelId)
    if (
      channel &&
      syncBackendMutation((session) =>
        patchBackendChannel(
          channelId,
          {
            health: channel.intakeEnabled ? 'paused' : 'healthy',
          },
          session,
        ),
      )
    ) {
      return
    }

    patchState((current) => ({
      ...current,
      channels: current.channels.map((channel) =>
        channel.id === channelId
          ? {
              ...channel,
              intakeEnabled: !channel.intakeEnabled,
              status: channel.intakeEnabled ? 'paused' : 'healthy',
            }
          : channel,
      ),
    }))
  }

  function toggleRule(ruleId: string) {
    const rule = state.rules.find((item) => item.id === ruleId)
    if (
      rule &&
      syncBackendMutation((session) =>
        patchBackendAutomationRule(
          ruleId,
          {
            enabled: rule.status !== 'active',
          },
          session,
        ),
      )
    ) {
      return
    }

    patchState((current) => ({
      ...current,
      rules: current.rules.map((rule) =>
        rule.id === ruleId
          ? { ...rule, status: rule.status === 'active' ? 'paused' : 'active' }
          : rule,
      ),
    }))
  }

  function publishArticle(articleId: string) {
    if (
      syncBackendMutation((session) =>
        patchBackendKnowledgeArticle(
          articleId,
          {
            status: 'published',
          },
          session,
        ),
      )
    ) {
      return
    }

    patchState((current) => ({
      ...current,
      articles: current.articles.map((article) =>
        article.id === articleId ? { ...article, status: 'published' } : article,
      ),
    }))
  }

  function createUser(input: BackendCreateUserInput) {
    return syncBackendMutation((session) => createBackendUser(input, session))
  }

  function updateUser(userId: string, patch: BackendUpdateUserInput) {
    return syncBackendMutation((session) => patchBackendUser(userId, patch, session))
  }

  function changePassword(currentPassword: string, newPassword: string) {
    return syncBackendMutation((session) =>
      changeBackendPassword(
        {
          current_password: currentPassword,
          new_password: newPassword,
        },
        session,
      ),
    )
  }

  function retryOutboundMessage(messageId: string) {
    return syncBackendMutation((session) => retryBackendOutboundMessage(messageId, session))
  }

  function updateHandoffStatus(handoffId: string, status: HandoffStatus) {
    const backendStatusValue =
      status === 'completed' ? 'resolved' : status === 'in-progress' ? 'accepted' : status

    if (
      syncBackendMutation((session) =>
        patchBackendHandoff(
          handoffId,
          {
            status: backendStatusValue,
          },
          session,
        ),
      )
    ) {
      return
    }

    const updatedAt = new Date().toISOString()
    patchState((current) => {
      const handoff = current.handoffs.find((item) => item.id === handoffId)
      const statusEvent: TimelineEvent | undefined = handoff
        ? {
            id: uid('event'),
            type: 'handoff',
            channelId: 'internal',
            author: 'Handoff desk',
            authorRole: 'system',
            timestamp: updatedAt,
            body: `${handoff.receivingTeam} handoff marked ${status}.`,
          }
        : undefined

      return {
        ...current,
        handoffs: current.handoffs.map((item) =>
          item.id === handoffId ? { ...item, status, updatedAt } : item,
        ),
        conversations: statusEvent
          ? current.conversations.map((conversation) =>
              conversation.id === handoff?.conversationId
                ? {
                    ...conversation,
                    status: status === 'completed' ? 'open' : conversation.status,
                    updatedAt,
                    timeline: [...conversation.timeline, statusEvent],
                  }
                : conversation,
            )
          : current.conversations,
      }
    })
  }

  function toggleHandoffChecklist(handoffId: string, taskId: string) {
    const handoff = state.handoffs.find((item) => item.id === handoffId)
    const task = handoff?.checklist.find((item) => item.id === taskId)
    if (
      handoff &&
      task &&
      syncBackendMutation((session) =>
        patchBackendHandoff(
          handoffId,
          {
            checklist_item_id: taskId,
            checklist_item_complete: !task.done,
          },
          session,
        ),
      )
    ) {
      return
    }

    patchState((current) => ({
      ...current,
      handoffs: current.handoffs.map((handoff) =>
        handoff.id === handoffId
          ? {
              ...handoff,
              updatedAt: new Date().toISOString(),
              checklist: handoff.checklist.map((task) =>
                task.id === taskId ? { ...task, done: !task.done } : task,
              ),
            }
          : handoff,
      ),
    }))
  }

  function resetDemo() {
    updateRoute({ screen: 'command', channel: null, conversation: null, customer: null })
    patchState(() => initialOmniState)
  }

  return {
    state,
    hydrated,
    online,
    metrics,
    selectedConversation,
    selectedCustomer,
    filteredConversations,
    selectScreen,
    selectConversation,
    selectCustomer,
    setSelectedChannel,
    setFilters,
    resetFilters,
    submitComposer,
    createConversation,
    updateConversation,
    toggleTask,
    toggleChannelIntake,
    toggleRule,
    publishArticle,
    createUser,
    updateUser,
    changePassword,
    retryOutboundMessage,
    updateSettings,
    updateHandoffStatus,
    toggleHandoffChecklist,
    resetDemo,
    backendSession,
    login,
    logout,
    switchMarket,
    backendSync,
    refreshBackend,
  }
}
