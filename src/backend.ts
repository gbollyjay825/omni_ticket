export interface BackendHealth {
  status: string
}

export interface BackendSettings {
  market_id: string
  ai_work_queue_automation_enabled: boolean
  ai_can_send_customer_messages: boolean
  default_timezone: string
  business_hours: string
  public_brand_name: string
}

export interface BackendAnalyticsSummary {
  open_tickets: number
  at_risk_tickets: number
  breached_tickets: number
  channel_volume?: Record<string, number>
  active_agents?: number
  avg_occupancy?: number
}

export interface BackendConnectorProvider {
  provider: string
  status: string
  market: string
  account: string | null
  production_dependencies: string[]
  supports: string[]
  intake_enabled?: boolean
  outbound_enabled?: boolean
  webhook_verified?: boolean
  secret_configured?: boolean
  failure_count?: number
}

export interface BackendConnectorAccount {
  id: string
  market_id: string
  provider: string
  display_name: string
  account_identifier: string
  status:
    | 'mocked'
    | 'connected'
    | 'pending_credentials'
    | 'action_required'
    | 'disabled'
    | 'error'
  intake_enabled: boolean
  outbound_enabled: boolean
  webhook_url: string
  webhook_verified: boolean
  credential_ref: string | null
  secret_configured: boolean
  last_sync_at: string | null
  last_error: string | null
  failure_count: number
  required_credentials: string[]
  capabilities: string[]
  created_at: string
  updated_at: string
}

export interface BackendOutboundMessage {
  id: string
  market_id: string
  ticket_id: string
  timeline_event_id: string | null
  connector_event_id: string | null
  provider: string
  status: 'queued' | 'sending' | 'sent' | 'failed' | 'retrying' | 'dead_lettered'
  actor: string
  body: string
  idempotency_key: string
  attempts: number
  max_attempts: number
  next_attempt_at: string | null
  sent_at: string | null
  last_error: string | null
  payload: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface BackendTrackerSummary {
  market_id: string
  market: string
  epics: string[]
  current_status: string
  known_dependencies: string[]
}

export interface BackendSnapshot {
  health: BackendHealth
  session: BackendAuthContext
  users: BackendUser[]
  settings: BackendSettings
  tracker: BackendTrackerSummary
  analytics: BackendAnalyticsSummary
  providers: BackendConnectorProvider[]
  connectorAccounts: BackendConnectorAccount[]
  outboundMessages: BackendOutboundMessage[]
  channels: BackendChannel[]
  agents: BackendAgent[]
  companies: BackendCompany[]
  customers: BackendCustomer[]
  tickets: BackendTicketContext[]
  handoffs: BackendHandoff[]
  connector_accounts: BackendConnectorAccount[]
  outbound_messages: BackendOutboundMessage[]
  knowledge: BackendKnowledgeArticle[]
  rules: BackendAutomationRule[]
}

export interface BackendSyncState {
  status: 'idle' | 'syncing' | 'connected' | 'error'
  baseUrl: string
  lastSyncAt?: string
  error?: string
  snapshot?: BackendSnapshot
}

export interface BackendMarket {
  id: string
  code: string
  name: string
  timezone: string
  currency: string
  default_locale: string
  support_email: string
  whatsapp_number?: string | null
  facebook_page?: string | null
  instagram_handle?: string | null
}

export interface BackendUser {
  id: string
  name: string
  email: string
  role: 'agent' | 'supervisor' | 'admin' | 'auditor'
  market_ids: string[]
  default_market_id: string
  active: boolean
}

export interface BackendAuthContext {
  user: BackendUser
  market: BackendMarket
}

export interface BackendSession extends BackendAuthContext {
  access_token: string
  token_type: string
  available_markets: BackendMarket[]
}

export interface BackendLoginInput {
  email: string
  password: string
  market_id?: string
}

export interface BackendChannel {
  id: string
  market_id: string
  type: string
  name: string
  handle: string
  health: 'healthy' | 'degraded' | 'paused'
  queued: number
  active: number
  sla_risk: number
  capabilities: string[]
}

export interface BackendAgent {
  id: string
  market_ids: string[]
  name: string
  email: string
  team: string
  status: 'available' | 'busy' | 'away' | 'offline'
  occupancy: number
  capacity: number
  skills: string[]
  languages: string[]
}

export interface BackendCompany {
  id: string
  market_id: string
  name: string
  tier: string
  health_score: number
  account_value: number
}

export interface BackendContactPoint {
  channel: string
  value: string
  verified: boolean
}

export interface BackendCustomer {
  id: string
  market_id: string
  name: string
  email: string
  company_id: string | null
  location: string
  sentiment: 'positive' | 'neutral' | 'frustrated' | 'angry'
  preferred_channels: string[]
  contact_points: BackendContactPoint[]
  tags: string[]
  notes: string
}

export interface BackendTicketTask {
  id: string
  label: string
  complete: boolean
}

export interface BackendSla {
  first_response_due_at: string
  resolution_due_at: string
  risk: 'on_track' | 'at_risk' | 'breached'
  breached: boolean
}

export interface BackendTimelineEvent {
  id: string
  ticket_id: string
  type: string
  channel: string
  actor: string
  body: string
  created_at: string
  public: boolean
  metadata: Record<string, unknown>
}

export interface BackendAiDecision {
  id: string
  ticket_id: string
  created_at: string
  decision_type: string
  confidence: number
  summary: string
  model_version: string
  input_reference: string
  override_allowed: boolean
}

export interface BackendTicket {
  id: string
  market_id: string
  public_id: string
  subject: string
  description: string
  customer_id: string
  channel: string
  status: 'open' | 'pending' | 'waiting' | 'solved' | 'closed'
  priority: 'low' | 'normal' | 'high' | 'urgent'
  sentiment: 'positive' | 'neutral' | 'frustrated' | 'angry'
  assignee_id: string | null
  team: string
  tags: string[]
  tasks: BackendTicketTask[]
  sla: BackendSla
  ai_summary: string
  recommended_action: string
  created_at: string
  updated_at: string
}

export interface BackendTicketContext {
  ticket: BackendTicket
  customer: BackendCustomer
  company: BackendCompany | null
  assignee: BackendAgent | null
  timeline: BackendTimelineEvent[]
  handoffs: BackendHandoff[]
  ai_decisions: BackendAiDecision[]
  outbound_messages: BackendOutboundMessage[]
}

export interface BackendHandoff {
  id: string
  market_id: string
  ticket_id: string
  from_team: string
  to_team: string
  requested_by: string
  reason: string
  status: 'requested' | 'accepted' | 'blocked' | 'resolved' | 'cancelled'
  due_at: string
  checklist: BackendTicketTask[]
  blocker: string | null
  created_at: string
  updated_at: string
}

export interface BackendKnowledgeArticle {
  id: string
  market_ids: string[]
  title: string
  status: string
  language: string
  channels: string[]
  tags: string[]
  body: string
  updated_at: string
}

export interface BackendAutomationRule {
  id: string
  market_id: string
  name: string
  enabled: boolean
  trigger: string
  action: string
  last_fired_at: string | null
  failure_count: number
}

export interface BackendCreateTicketInput {
  subject: string
  description: string
  customer_id: string
  channel: string
  priority?: BackendTicket['priority']
  tags?: string[]
}

export interface BackendUpdateTicketInput {
  status?: BackendTicket['status']
  priority?: BackendTicket['priority']
  assignee_id?: string | null
  tags?: string[]
}

export interface BackendReplyInput {
  channel: string
  actor: string
  body: string
  public: boolean
  idempotency_key?: string
}

export interface BackendCreateHandoffInput {
  to_team: string
  requested_by: string
  reason: string
  due_minutes: number
  checklist: string[]
}

export interface BackendUpdateHandoffInput {
  status?: BackendHandoff['status']
  blocker?: string | null
  checklist_item_id?: string
  checklist_item_complete?: boolean
}

export interface BackendUpdateChannelInput {
  health?: BackendChannel['health']
  queued?: number
  active?: number
  sla_risk?: number
}

export interface BackendUpdateKnowledgeInput {
  status?: BackendKnowledgeArticle['status']
}

export interface BackendUpdateRuleInput {
  enabled?: boolean
}

export interface BackendCreateUserInput {
  name: string
  email: string
  role: BackendUser['role']
  market_ids: string[]
  default_market_id?: string
  active?: boolean
}

export interface BackendUpdateUserInput {
  name?: string
  email?: string
  role?: BackendUser['role']
  market_ids?: string[]
  default_market_id?: string
  active?: boolean
}

interface BackendFrontendSnapshot {
  session: BackendAuthContext
  users: BackendUser[]
  settings: BackendSettings
  channels: BackendChannel[]
  agents: BackendAgent[]
  companies: BackendCompany[]
  customers: BackendCustomer[]
  tickets: BackendTicketContext[]
  handoffs: BackendHandoff[]
  connector_accounts: BackendConnectorAccount[]
  knowledge: BackendKnowledgeArticle[]
  rules: BackendAutomationRule[]
  outbound_messages: BackendOutboundMessage[]
  analytics: BackendAnalyticsSummary
  tracker: BackendTrackerSummary
}

function trimTrailingSlash(value: string) {
  return value.endsWith('/') ? value.slice(0, -1) : value
}

export function getBackendBaseUrl() {
  const configured = import.meta.env.VITE_OMNI_API_BASE_URL
  return trimTrailingSlash(configured || 'http://127.0.0.1:8000/api/v1')
}

function authHeaders(session?: BackendSession | null) {
  if (!session) return {}
  return {
    Authorization: `Bearer ${session.access_token}`,
    'X-Omni-Market': session.market.id,
  }
}

async function fetchJson<T>(
  path: string,
  init?: RequestInit,
  session?: BackendSession | null,
): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  Object.entries(authHeaders(session)).forEach(([key, value]) => headers.set(key, value))

  const response = await fetch(`${getBackendBaseUrl()}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`.trim()
    try {
      const errorBody = (await response.json()) as { detail?: string }
      if (errorBody.detail) {
        message = errorBody.detail
      }
    } catch {
      // Keep the HTTP status when the server does not return a JSON problem body.
    }
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

export async function loginBackend(input: BackendLoginInput): Promise<BackendSession> {
  return fetchJson<BackendSession>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function fetchBackendSnapshot(
  session: BackendSession,
  signal?: AbortSignal,
): Promise<BackendSnapshot> {
  const [health, providers, frontendSnapshot] = await Promise.all([
    fetchJson<BackendHealth>('/health', { signal }),
    fetchJson<BackendConnectorProvider[]>('/connectors/providers', { signal }, session),
    fetchJson<BackendFrontendSnapshot>('/frontend/snapshot', { signal }, session),
  ])

  return {
    health,
    providers,
    connectorAccounts: frontendSnapshot.connector_accounts,
    outboundMessages: frontendSnapshot.outbound_messages,
    ...frontendSnapshot,
  }
}

export async function patchBackendSettings(
  patch: Partial<BackendSettings>,
  session: BackendSession,
): Promise<BackendSettings> {
  return fetchJson<BackendSettings>('/settings', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }, session)
}

export async function createBackendUser(
  input: BackendCreateUserInput,
  session: BackendSession,
): Promise<BackendUser> {
  return fetchJson<BackendUser>(
    '/auth/users',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendUser(
  userId: string,
  patch: BackendUpdateUserInput,
  session: BackendSession,
): Promise<BackendUser> {
  return fetchJson<BackendUser>(
    `/auth/users/${userId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function createBackendTicket(
  input: BackendCreateTicketInput,
  session: BackendSession,
): Promise<BackendTicket> {
  return fetchJson<BackendTicket>(
    '/tickets',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendTicket(
  ticketId: string,
  patch: BackendUpdateTicketInput,
  session: BackendSession,
): Promise<BackendTicket> {
  return fetchJson<BackendTicket>(
    `/tickets/${ticketId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function postBackendReply(
  ticketId: string,
  input: BackendReplyInput,
  session: BackendSession,
): Promise<BackendTimelineEvent> {
  return fetchJson<BackendTimelineEvent>(
    `/tickets/${ticketId}/reply`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function createBackendHandoff(
  ticketId: string,
  input: BackendCreateHandoffInput,
  session: BackendSession,
): Promise<BackendHandoff> {
  return fetchJson<BackendHandoff>(
    `/tickets/${ticketId}/handoffs`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendHandoff(
  handoffId: string,
  patch: BackendUpdateHandoffInput,
  session: BackendSession,
): Promise<BackendHandoff> {
  return fetchJson<BackendHandoff>(
    `/handoffs/${handoffId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function patchBackendChannel(
  channelId: string,
  patch: BackendUpdateChannelInput,
  session: BackendSession,
): Promise<BackendChannel> {
  return fetchJson<BackendChannel>(
    `/channels/${channelId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function patchBackendKnowledgeArticle(
  articleId: string,
  patch: BackendUpdateKnowledgeInput,
  session: BackendSession,
): Promise<BackendKnowledgeArticle> {
  return fetchJson<BackendKnowledgeArticle>(
    `/knowledge/${articleId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function patchBackendAutomationRule(
  ruleId: string,
  patch: BackendUpdateRuleInput,
  session: BackendSession,
): Promise<BackendAutomationRule> {
  return fetchJson<BackendAutomationRule>(
    `/automation-rules/${ruleId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function retryBackendOutboundMessage(
  messageId: string,
  session: BackendSession,
): Promise<BackendOutboundMessage> {
  return fetchJson<BackendOutboundMessage>(
    `/outbound/messages/${messageId}/retry`,
    {
      method: 'POST',
      body: JSON.stringify({ reason: 'Manual retry from Setup' }),
    },
    session,
  )
}
