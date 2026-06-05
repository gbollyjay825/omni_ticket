// Pure, dependency-free helpers for the Omnichannel Dashboard (B-110).
// Everything here is computed from data already present in the frontend snapshot
// (conversations with their timelines + backend CSAT feedback) so the dashboard
// shows live numbers and supports instant client-side filtering — no hardcoded tiles.

import type { ChannelId, OmniConversation, TimelineType } from './domain'

// Channels we treat as "chat / messaging" for the chat-side dashboard tiles.
// Everything else (email, phone, portal, api, internal) is "ticket" volume.
export const CHAT_CHANNEL_IDS: ChannelId[] = ['whatsapp', 'instagram', 'facebook', 'chat', 'sms']

export function isChatChannel(channelId: ChannelId): boolean {
  return CHAT_CHANNEL_IDS.includes(channelId)
}

// CSAT feedback as delivered in the backend snapshot (snake_case from the API).
export interface CsatFeedbackRecord {
  id: string
  ticket_id: string
  rating: number
  comment?: string | null
  source?: string
  created_at: string
}

export type DashboardRange = 'today' | '7d' | '30d' | 'all'

export const DASHBOARD_RANGES: { id: DashboardRange; label: string }[] = [
  { id: 'today', label: 'Today' },
  { id: '7d', label: 'Last 7 days' },
  { id: '30d', label: 'Last 30 days' },
  { id: 'all', label: 'All time' },
]

export interface DashboardFilters {
  range: DashboardRange
  ticketGroup: string // 'all' or a support-group name
  chatGroup: string // 'all' or a support-group name
}

export interface RecentActivityItem {
  id: string
  conversationId: string
  ticketNumber: string
  type: TimelineType
  actor: string
  body: string
  timestamp: string
}

export interface DashboardMetrics {
  ticketTrends: { open: number; unassigned: number; overdue: number; dueToday: number }
  ticketPerformance: { avgFirstResponse: string; resolutionWithinSla: string; hasData: boolean }
  ticketCsat: {
    responses: number
    positivePct: number
    neutralPct: number
    negativePct: number
  }
  chatTrends: { unassigned: number; assignedNotReplied: number; assigned: number }
  chatPerformance: {
    firstResponse: string
    response: string
    resolution: string
    wait: string
    hasData: boolean
  }
  chatCsat: {
    responses: number
    avgRating: string
    stars: number
    yesCount: number
    noCount: number
    yesPct: number
    noPct: number
  }
  recentActivity: RecentActivityItem[]
}

const DAY_MS = 24 * 60 * 60 * 1000

function rangeStart(range: DashboardRange, now: number): number {
  switch (range) {
    case 'today':
      return now - DAY_MS
    case '7d':
      return now - 7 * DAY_MS
    case '30d':
      return now - 30 * DAY_MS
    case 'all':
    default:
      return Number.NEGATIVE_INFINITY
  }
}

function withinRange(timestamp: string, start: number): boolean {
  if (start === Number.NEGATIVE_INFINITY) return true
  const ms = new Date(timestamp).getTime()
  return Number.isFinite(ms) && ms >= start
}

function average(values: number[]): number | null {
  if (values.length === 0) return null
  return values.reduce((total, value) => total + value, 0) / values.length
}

function round1(value: number): number {
  return Math.round(value * 10) / 10
}

/** Human-friendly duration, e.g. 32182 -> "8h 56m 22s". Returns "—" for no data. */
export function formatDuration(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return '—'
  const total = Math.round(seconds)
  if (total < 60) return `${total}s`
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const parts: string[] = []
  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0 || hours > 0) parts.push(`${minutes}m`)
  parts.push(`${secs}s`)
  return parts.join(' ')
}

/** Seconds from ticket creation to the first agent reply, or null if none. */
export function firstResponseSeconds(conversation: OmniConversation): number | null {
  const created = new Date(conversation.createdAt).getTime()
  if (!Number.isFinite(created)) return null
  const firstReply = conversation.timeline
    .filter((event) => event.type === 'agent-reply' || event.authorRole === 'agent')
    .map((event) => new Date(event.timestamp).getTime())
    .filter((ms) => Number.isFinite(ms) && ms >= created)
    .sort((a, b) => a - b)[0]
  if (firstReply == null) return null
  return (firstReply - created) / 1000
}

/** Average gap (seconds) between an inbound customer message and the next agent reply. */
export function averageResponseSeconds(conversation: OmniConversation): number | null {
  const gaps: number[] = []
  let pendingCustomerAt: number | null = null
  for (const event of conversation.timeline) {
    const ms = new Date(event.timestamp).getTime()
    if (!Number.isFinite(ms)) continue
    const fromCustomer = event.authorRole === 'customer' || event.type === 'customer-message'
    const fromAgent = event.authorRole === 'agent' || event.type === 'agent-reply'
    if (fromCustomer) {
      if (pendingCustomerAt == null) pendingCustomerAt = ms
    } else if (fromAgent && pendingCustomerAt != null) {
      gaps.push((ms - pendingCustomerAt) / 1000)
      pendingCustomerAt = null
    }
  }
  return average(gaps)
}

/** Seconds from creation to resolution for resolved tickets, else null. */
export function resolutionSeconds(conversation: OmniConversation): number | null {
  if (conversation.status !== 'resolved') return null
  const created = new Date(conversation.createdAt).getTime()
  const resolved = new Date(conversation.updatedAt).getTime()
  if (!Number.isFinite(created) || !Number.isFinite(resolved) || resolved < created) return null
  return (resolved - created) / 1000
}

function pct(part: number, whole: number): number {
  if (whole <= 0) return 0
  return Math.round((part / whole) * 100)
}

export function computeDashboardMetrics(
  conversations: OmniConversation[],
  csatFeedback: CsatFeedbackRecord[],
  filters: DashboardFilters,
  now: number,
): DashboardMetrics {
  const start = rangeStart(filters.range, now)

  const inRange = conversations.filter((conversation) => withinRange(conversation.createdAt, start))
  const ticketConversations = inRange.filter(
    (conversation) =>
      !isChatChannel(conversation.channelId) &&
      (filters.ticketGroup === 'all' || conversation.group === filters.ticketGroup),
  )
  const chatConversations = inRange.filter(
    (conversation) =>
      isChatChannel(conversation.channelId) &&
      (filters.chatGroup === 'all' || conversation.group === filters.chatGroup),
  )

  // ── Ticket trends ────────────────────────────────────────────────────────
  const openTickets = ticketConversations.filter((conversation) => conversation.status !== 'resolved')
  const ticketTrends = {
    open: openTickets.length,
    unassigned: ticketConversations.filter(
      (conversation) =>
        conversation.status !== 'resolved' &&
        (conversation.status === 'new' || conversation.assigneeId === ''),
    ).length,
    overdue: openTickets.filter((conversation) => conversation.slaState === 'breached').length,
    dueToday: openTickets.filter(
      (conversation) => new Date(conversation.resolutionDue).getTime() - now < DAY_MS,
    ).length,
  }

  // ── Ticket performance ───────────────────────────────────────────────────
  const ticketFrt = average(
    ticketConversations
      .map((conversation) => firstResponseSeconds(conversation))
      .filter((value): value is number => value != null),
  )
  const resolvedTickets = ticketConversations.filter((conversation) => conversation.status === 'resolved')
  const withinSla = resolvedTickets.filter((conversation) => conversation.slaState !== 'breached').length
  const ticketPerformance = {
    avgFirstResponse: formatDuration(ticketFrt),
    resolutionWithinSla: resolvedTickets.length > 0 ? `${pct(withinSla, resolvedTickets.length)}%` : '—',
    hasData: ticketConversations.length > 0,
  }

  // ── CSAT (joined to conversations by ticket id, split chat vs ticket) ──────
  const conversationById = new Map(conversations.map((conversation) => [conversation.id, conversation]))
  const csatInRange = csatFeedback.filter((record) => withinRange(record.created_at, start))
  const ticketCsatRecords = csatInRange.filter((record) => {
    const conversation = conversationById.get(record.ticket_id)
    return conversation != null && !isChatChannel(conversation.channelId)
  })
  const chatCsatRecords = csatInRange.filter((record) => {
    const conversation = conversationById.get(record.ticket_id)
    return conversation != null && isChatChannel(conversation.channelId)
  })

  const ticketPositive = ticketCsatRecords.filter((record) => record.rating >= 4).length
  const ticketNeutral = ticketCsatRecords.filter((record) => record.rating === 3).length
  const ticketNegative = ticketCsatRecords.filter((record) => record.rating <= 2).length
  const ticketCsat = {
    responses: ticketCsatRecords.length,
    positivePct: pct(ticketPositive, ticketCsatRecords.length),
    neutralPct: pct(ticketNeutral, ticketCsatRecords.length),
    negativePct: pct(ticketNegative, ticketCsatRecords.length),
  }

  // ── Chat trends ──────────────────────────────────────────────────────────
  const chatTrends = {
    unassigned: chatConversations.filter((conversation) => conversation.status === 'new').length,
    assignedNotReplied: chatConversations.filter(
      (conversation) => conversation.status !== 'resolved' && conversation.slaState !== 'healthy',
    ).length,
    assigned: chatConversations.filter((conversation) => conversation.status !== 'resolved').length,
  }

  // ── Chat performance ─────────────────────────────────────────────────────
  const chatFrt = average(
    chatConversations
      .map((conversation) => firstResponseSeconds(conversation))
      .filter((value): value is number => value != null),
  )
  const chatResp = average(
    chatConversations
      .map((conversation) => averageResponseSeconds(conversation))
      .filter((value): value is number => value != null),
  )
  const chatRes = average(
    chatConversations
      .map((conversation) => resolutionSeconds(conversation))
      .filter((value): value is number => value != null),
  )
  const chatPerformance = {
    firstResponse: formatDuration(chatFrt),
    response: formatDuration(chatResp),
    resolution: formatDuration(chatRes),
    wait: formatDuration(chatFrt),
    hasData: chatConversations.length > 0,
  }

  // ── Chat CSAT (thumbs up / down style) ───────────────────────────────────
  const chatYes = chatCsatRecords.filter((record) => record.rating >= 4).length
  const chatNo = chatCsatRecords.filter((record) => record.rating <= 3).length
  const chatAvg = average(chatCsatRecords.map((record) => record.rating))
  const chatCsat = {
    responses: chatCsatRecords.length,
    avgRating: chatAvg == null ? '—' : `${round1(chatAvg)}/5`,
    stars: chatAvg == null ? 0 : Math.round(chatAvg),
    yesCount: chatYes,
    noCount: chatNo,
    yesPct: pct(chatYes, chatCsatRecords.length),
    noPct: pct(chatNo, chatCsatRecords.length),
  }

  // ── Recent activity (latest timeline events across in-range conversations) ─
  const recentActivity: RecentActivityItem[] = inRange
    .flatMap((conversation) =>
      conversation.timeline.map((event) => ({
        id: event.id,
        conversationId: conversation.id,
        ticketNumber: conversation.ticketNumber,
        type: event.type,
        actor: event.author,
        body: event.body,
        timestamp: event.timestamp,
      })),
    )
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 8)

  return {
    ticketTrends,
    ticketPerformance,
    ticketCsat,
    chatTrends,
    chatPerformance,
    chatCsat,
    recentActivity,
  }
}
