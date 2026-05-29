import { useEffect, useMemo, useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  Building2,
  Check,
  CheckCircle2,
  ClipboardList,
  Clock,
  Code2,
  Command,
  Filter,
  Gauge,
  GitBranch,
  Globe2,
  Handshake,
  Headphones,
  Inbox,
  Languages,
  LifeBuoy,
  Lock,
  Mail,
  MessageCircle,
  MessageSquare,
  Paperclip,
  Phone,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Timer,
  UserCheck,
  Users,
  Wifi,
  WifiOff,
  Workflow,
  X,
} from 'lucide-react'
import type {
  ChannelId,
  ComposerMode,
  ContactMethod,
  ConversationStatus,
  HandoffStatus,
  NewTicketInput,
  OmniConversation,
  Priority,
  ScreenId,
  Sentiment,
  SlaState,
} from './domain'
import { useOmniStore } from './store'
import './App.css'

const screenConfig: { id: ScreenId; label: string; icon: LucideIcon }[] = [
  { id: 'command', label: 'Command Center', icon: Command },
  { id: 'inbox', label: 'Work Queue', icon: Inbox },
  { id: 'channels', label: 'Channel Chats', icon: MessageCircle },
  { id: 'customers', label: 'Customer 360', icon: Users },
  { id: 'knowledge', label: 'Answers', icon: BookOpen },
  { id: 'automation', label: 'Rules & Promises', icon: Workflow },
  { id: 'handoffs', label: 'Team Handoffs', icon: Handshake },
  { id: 'analytics', label: 'Insights', icon: BarChart3 },
  { id: 'workforce', label: 'Staffing', icon: UserCheck },
  { id: 'admin', label: 'Setup', icon: Settings },
  { id: 'tracker', label: 'Delivery Plan', icon: GitBranch },
]

const channelIcons: Record<ChannelId, LucideIcon> = {
  email: Mail,
  chat: MessageCircle,
  phone: Phone,
  whatsapp: MessageSquare,
  sms: MessageSquare,
  instagram: MessageCircle,
  facebook: MessageCircle,
  portal: Globe2,
  api: Code2,
  internal: Handshake,
}

const priorityOptions: (Priority | 'all')[] = ['all', 'urgent', 'high', 'medium', 'low']
const directMessageChannelIds: ChannelId[] = ['whatsapp', 'instagram', 'facebook']
const screenLead: Record<ScreenId, string> = {
  command: 'One view of demand, risk, team load, and the manager decisions needed today.',
  inbox: 'Prioritized customer work with history, owner, promise time, and next action in one place.',
  channels: 'WhatsApp, Instagram, and Facebook stay as native chat windows while still rolling into tickets.',
  customers: 'Customer profile, open value, history, mood, and preferred contact routes.',
  knowledge: 'Approved answers agents can reuse to resolve faster and reduce repeat work.',
  automation: 'Clear routing and response promises that keep work moving without manual chasing.',
  handoffs: 'Cross-team work with owner, due time, blockers, and closure checklist.',
  analytics: 'Executive service signals across volume, timeliness, quality, and staffing pressure.',
  workforce: 'Agent availability, load, skills, and shift coverage for real-time balancing.',
  admin: 'Simple controls for people, channels, fields, security, and operating readiness.',
  tracker: 'What is complete, what is pending, and what remains before production buildout.',
}
const handoffTeams = [
  'Billing Operations',
  'Fulfillment',
  'Engineering',
  'Account Operations',
  'Compliance',
]
const userRoleOptions = ['agent', 'supervisor', 'admin', 'auditor'] as const
const handoffStatusOrder: HandoffStatus[] = ['requested', 'accepted', 'in-progress', 'blocked', 'completed']
const statusOptions: (ConversationStatus | 'all')[] = [
  'all',
  'new',
  'open',
  'pending',
  'waiting',
  'resolved',
]
const slaOptions: (SlaState | 'all')[] = ['all', 'healthy', 'risk', 'breached', 'paused']
const sentimentOptions: (Sentiment | 'all')[] = [
  'all',
  'positive',
  'neutral',
  'frustrated',
  'at-risk',
]

const macros = [
  'Thanks for reaching out. I am reviewing the full conversation history and will keep this thread updated with the next confirmed action.',
  'I can see this is time-sensitive. I am escalating it now and will share the owner, status, and next update time in this thread.',
  'I found the relevant help article and included the key steps below. I will keep the ticket open until you confirm it resolves the issue.',
]

const composerModeLabels: Record<ComposerMode, string> = {
  reply: 'Customer reply',
  note: 'Internal note',
  handoff: 'Team handoff',
}

const slaLabels: Record<SlaState, string> = {
  healthy: 'On track',
  risk: 'At risk',
  breached: 'Overdue',
  paused: 'Paused',
}

const handoffStatusLabels: Record<HandoffStatus, string> = {
  requested: 'New request',
  accepted: 'Accepted',
  'in-progress': 'Working',
  blocked: 'Blocked',
  completed: 'Done',
}

const sentimentLabels: Record<Sentiment, string> = {
  positive: 'Positive',
  neutral: 'Neutral',
  frustrated: 'Frustrated',
  'at-risk': 'At risk',
}

function titleCase(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function initials(value: string) {
  return value
    .split(' ')
    .map((part) => part[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('en-NG', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function percent(value: number, total: number) {
  return total === 0 ? 0 : Math.round((value / total) * 100)
}

function queueNoun(value: number) {
  return value === 1 ? 'customer' : 'customers'
}

function isDirectMessageChannel(channelId: ChannelId | 'all'): channelId is ChannelId {
  return channelId !== 'all' && directMessageChannelIds.includes(channelId)
}

type AppRouteParams = {
  screen?: ScreenId
  channel?: ChannelId | 'all'
  conversation?: string
  customer?: string
}

function routeHref(params: AppRouteParams) {
  const url =
    typeof window === 'undefined'
      ? new URL('https://omni-ticket.local/')
      : new URL(window.location.href)

  if (params.screen) {
    if (params.channel === undefined) url.searchParams.delete('channel')
    if (params.conversation === undefined) url.searchParams.delete('conversation')
    if (params.customer === undefined) url.searchParams.delete('customer')
  }

  Object.entries(params).forEach(([key, value]) => {
    if (!value || value === 'all') {
      url.searchParams.delete(key)
      return
    }
    url.searchParams.set(key, value)
  })

  return `${url.pathname}${url.search}${url.hash}`
}

function contactHref(method: ContactMethod, customerId: string) {
  const cleanValue = method.value.replace(/\s+/g, '')
  if (method.type === 'email') return `mailto:${method.value}`
  if (method.type === 'phone') return `tel:${cleanValue}`
  if (method.type === 'sms') return `sms:${cleanValue}`
  if (method.type === 'portal') return routeHref({ screen: 'channels', channel: 'portal', customer: customerId })
  if (method.type === 'whatsapp') return routeHref({ screen: 'channels', channel: 'whatsapp', customer: customerId })
  return routeHref({ screen: 'channels', channel: 'facebook', customer: customerId })
}

const priorityRank: Record<Priority, number> = {
  urgent: 4,
  high: 3,
  medium: 2,
  low: 1,
}

const slaRank: Record<SlaState, number> = {
  breached: 4,
  risk: 3,
  paused: 2,
  healthy: 1,
}

const sentimentRank: Record<Sentiment, number> = {
  'at-risk': 4,
  frustrated: 3,
  neutral: 2,
  positive: 1,
}

function triageScore(conversation: OmniConversation) {
  return (
    priorityRank[conversation.priority] * 24 +
    slaRank[conversation.slaState] * 18 +
    sentimentRank[conversation.sentiment] * 12 +
    (conversation.unread ? 10 : 0)
  )
}

function promiseTarget(conversation: OmniConversation) {
  return conversation.status === 'new' ? conversation.firstResponseDue : conversation.resolutionDue
}

function promiseLabel(conversation: OmniConversation) {
  const target = formatTime(promiseTarget(conversation))
  if (conversation.slaState === 'breached') return `Overdue since ${target}`
  if (conversation.slaState === 'risk') return `Due soon ${target}`
  if (conversation.slaState === 'paused') return `Paused until owner confirms`
  return `Due ${target}`
}

function channelWorkMode(channelId: ChannelId) {
  if (channelId === 'phone') return 'Call or callback'
  if (channelId === 'email') return 'Email reply'
  if (channelId === 'sms') return 'SMS update'
  if (channelId === 'portal') return 'Portal reply'
  if (channelId === 'api') return 'Partner update'
  if (channelId === 'internal') return 'Internal handoff'
  if (isDirectMessageChannel(channelId)) return 'Native chat'
  return 'Customer reply'
}

function connectorStatusLabel(status: string) {
  if (status === 'mocked') return 'local dev'
  return status.replaceAll('_', ' ')
}

function connectorStatusTone(status: string) {
  if (status === 'connected' || status === 'mocked') return 'healthy'
  if (status === 'action_required' || status === 'error') return 'degraded'
  if (status === 'disabled') return 'paused'
  return 'pending'
}

function deliveryLabel(status: NonNullable<OmniConversation['timeline'][number]['deliveryState']>) {
  if (status === 'dead_lettered') return 'Dead-lettered'
  if (status === 'retrying') return 'Retrying'
  if (status === 'sending') return 'Sending'
  if (status === 'failed') return 'Delivery failed'
  if (status === 'queued') return 'Queued for send'
  return 'Sent'
}

function OmniApp() {
  const {
    state,
    online,
    metrics,
    backendSync,
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
    retryOutboundMessage,
    updateSettings,
    updateHandoffStatus,
    toggleHandoffChecklist,
    resetDemo,
    backendSession,
    login,
    logout,
    switchMarket,
    refreshBackend,
  } = useOmniStore()

  const [composerMode, setComposerMode] = useState<ComposerMode>('reply')
  const [composerChannel, setComposerChannel] = useState<ChannelId>(selectedConversation.channelId)
  const [composerText, setComposerText] = useState('')
  const [handoffTeam, setHandoffTeam] = useState(handoffTeams[0])
  const [handoffReason, setHandoffReason] = useState('Operational support required')
  const [liveChatDraft, setLiveChatDraft] = useState('')
  const [translationOn, setTranslationOn] = useState(false)
  const [prototypeNotice, setPrototypeNotice] = useState('')
  const [quickCreateOpen, setQuickCreateOpen] = useState(false)
  const [notificationOpen, setNotificationOpen] = useState(false)
  const [attachmentReady, setAttachmentReady] = useState(false)
  const [loginEmail, setLoginEmail] = useState('gbolahan@omniticket.example.com')
  const [loginPassword, setLoginPassword] = useState('omni-demo')
  const [loginMarket, setLoginMarket] = useState('market-ng')
  const [quickTicket, setQuickTicket] = useState<NewTicketInput>({
    customerId: state.customers[0]?.id ?? '',
    channelId: 'email',
    subject: '',
    body: '',
    priority: 'medium',
    group: 'General Support',
    assigneeId: state.agents[0]?.id ?? '',
  })
  const [newUser, setNewUser] = useState({
    name: '',
    email: '',
    role: 'agent' as (typeof userRoleOptions)[number],
    marketIds: ['market-ng'],
    defaultMarketId: 'market-ng',
  })

  const selectedAgent = state.agents.find((agent) => agent.id === selectedConversation.assigneeId)
  const selectedChannel =
    state.channels.find((channel) => channel.id === selectedConversation.channelId) ?? state.channels[0]
  const focusedChannel =
    state.channels.find((channel) => channel.id === state.selectedChannelId) ?? undefined

  const channelTotals = useMemo(() => {
    return state.channels.map((channel) => ({
      channel,
      conversations: state.conversations.filter((conversation) => conversation.channelId === channel.id),
    }))
  }, [state.channels, state.conversations])

  const prioritizedWork = useMemo(
    () =>
      state.conversations
        .filter((conversation) => conversation.status !== 'resolved')
        .map((conversation) => ({
          conversation,
          customer: state.customers.find((customer) => customer.id === conversation.customerId),
          channel: state.channels.find((channel) => channel.id === conversation.channelId),
          owner: state.agents.find((agent) => agent.id === conversation.assigneeId),
          score: triageScore(conversation),
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 5),
    [state.agents, state.channels, state.conversations, state.customers],
  )

  const selectedCustomerOpenWork = state.conversations.filter(
    (conversation) =>
      conversation.customerId === selectedCustomer.id && conversation.status !== 'resolved',
  )
  const selectedHandoffs = state.handoffs.filter(
    (handoff) =>
      handoff.conversationId === selectedConversation.id && handoff.status !== 'completed',
  )
  const aiWorkQueueAutomationEnabled = state.settings?.aiWorkQueueAutomationEnabled ?? true
  const backendSnapshot = backendSync.snapshot
  const currentMarket = backendSession?.market
  const availableMarkets = backendSession?.available_markets ?? []

  const activeDirectChannelId = isDirectMessageChannel(state.selectedChannelId)
    ? state.selectedChannelId
    : 'whatsapp'

  const riskNotifications = state.conversations
    .filter((conversation) => conversation.slaState !== 'healthy')
    .slice(0, 4)
    .map((conversation) => ({
      id: conversation.id,
      title: conversation.ticketNumber,
      body: conversation.copilot.slaReason,
      action: () => openConversationInInbox(conversation),
      href: routeHref({ screen: 'inbox', conversation: conversation.id, customer: conversation.customerId }),
    }))
  const blockedNotifications = state.handoffs
    .filter((handoff) => handoff.status === 'blocked')
    .slice(0, 2)
    .map((handoff) => {
      const conversation = state.conversations.find((item) => item.id === handoff.conversationId)
      return {
        id: handoff.id,
        title: handoff.id,
        body: `${handoff.receivingTeam} is blocked on ${handoff.ticketNumber}.`,
        action: () => selectScreen('handoffs'),
        href: conversation
          ? routeHref({ screen: 'handoffs', conversation: conversation.id, customer: conversation.customerId })
          : routeHref({ screen: 'handoffs' }),
      }
    })
  const serviceNotifications = [
    ...riskNotifications,
    ...blockedNotifications,
    {
      id: 'knowledge-gap',
      title: 'Missing answer',
      body: 'Social complaint guidance needs approval before volume rises further.',
      action: () => selectScreen('knowledge'),
      href: routeHref({ screen: 'knowledge' }),
    },
  ]

  useEffect(() => {
    if (!prototypeNotice) return undefined
    const timer = window.setTimeout(() => setPrototypeNotice(''), 2600)
    return () => window.clearTimeout(timer)
  }, [prototypeNotice])

  function toggleNewUserMarket(marketId: string) {
    setNewUser((current) => {
      const nextMarketIds = current.marketIds.includes(marketId)
        ? current.marketIds.filter((item) => item !== marketId)
        : [...current.marketIds, marketId]
      const marketIds = nextMarketIds.length > 0 ? nextMarketIds : [marketId]
      const defaultMarketId = marketIds.includes(current.defaultMarketId)
        ? current.defaultMarketId
        : marketIds[0]
      return { ...current, marketIds, defaultMarketId }
    })
  }

  function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = newUser.name.trim()
    const email = newUser.email.trim().toLowerCase()
    if (!name || !email || !currentMarket) return

    const marketIds = newUser.marketIds.length > 0 ? newUser.marketIds : [currentMarket.id]
    const defaultMarketId = marketIds.includes(newUser.defaultMarketId)
      ? newUser.defaultMarketId
      : marketIds[0]

    if (
      createUser({
        name,
        email,
        role: newUser.role,
        market_ids: marketIds,
        default_market_id: defaultMarketId,
        active: true,
      })
    ) {
      setNewUser({
        name: '',
        email: '',
        role: 'agent',
        marketIds: [currentMarket.id],
        defaultMarketId: currentMarket.id,
      })
      setPrototypeNotice('User saved to the backend.')
    }
  }

  if (!backendSession) {
    return (
      <main className="login-shell">
        <section className="login-panel">
          <div className="brand-mark">
            <LifeBuoy size={24} />
          </div>
          <span>OMNI TICKET SECURE ACCESS</span>
          <h1>Sign in to your market workspace</h1>
          <p>
            One SPA serves every market. Your sign-in controls the market, email accounts,
            channel numbers, customers, tickets, and support rules you can access.
          </p>
          <form
            className="login-form"
            onSubmit={(event) => {
              event.preventDefault()
              login({ email: loginEmail, password: loginPassword, market_id: loginMarket })
            }}
          >
            <label>
              Email
              <input
                type="email"
                value={loginEmail}
                onChange={(event) => setLoginEmail(event.target.value)}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
              />
            </label>
            <label>
              Market
              <select value={loginMarket} onChange={(event) => setLoginMarket(event.target.value)}>
                <option value="market-ng">Nigeria</option>
                <option value="market-gh">Ghana</option>
                <option value="market-uk">United Kingdom</option>
              </select>
            </label>
            <button type="submit">
              <Lock size={16} />
              Sign in
            </button>
          </form>
          {backendSync.error ? <strong className="login-error">{backendSync.error}</strong> : null}
          <div className="login-demo-users">
            <button
              type="button"
              onClick={() => {
                setLoginEmail('gbolahan@omniticket.example.com')
                setLoginMarket('market-ng')
              }}
            >
              Admin · all markets
            </button>
            <button
              type="button"
              onClick={() => {
                setLoginEmail('kofi.gh@omniticket.example.com')
                setLoginMarket('market-gh')
              }}
            >
              Ghana agent
            </button>
          </div>
        </section>
      </main>
    )
  }

  function handleAppLink(event: MouseEvent<HTMLAnchorElement>, action: () => void) {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.altKey ||
      event.ctrlKey ||
      event.shiftKey
    ) {
      return
    }
    event.preventDefault()
    action()
  }

  function announcePrototype(message: string) {
    setPrototypeNotice(message)
  }

  function updateQuickTicket(patch: Partial<NewTicketInput>) {
    setQuickTicket((current) => ({ ...current, ...patch }))
  }

  function openQuickCreate(channelId: ChannelId = 'email') {
    setQuickTicket((current) => ({
      ...current,
      customerId: selectedCustomer.id,
      channelId,
      assigneeId: selectedAgent?.id ?? state.agents[0]?.id ?? current.assigneeId,
      group: selectedConversation.group || current.group,
    }))
    setQuickCreateOpen(true)
  }

  function submitQuickTicket() {
    if (!quickTicket.subject.trim() || !quickTicket.body.trim()) return
    createConversation(quickTicket)
    setQuickCreateOpen(false)
    setQuickTicket((current) => ({ ...current, subject: '', body: '' }))
    announcePrototype('New ticket created and opened in the Work Queue.')
  }

  function openConversation(conversation: OmniConversation) {
    setComposerChannel(conversation.channelId)
    setComposerText('')
    selectConversation(conversation.id)
  }

  function openConversationInInbox(conversation: OmniConversation) {
    openConversation(conversation)
    selectScreen('inbox')
  }

  function openWorkQueueFocus(
    filters: Partial<typeof state.filters>,
    conversation?: OmniConversation,
  ) {
    resetFilters()
    if (Object.keys(filters).length > 0) setFilters(filters)
    if (conversation) {
      openConversationInInbox(conversation)
      return
    }
    selectScreen('inbox')
  }

  function openDirectChannel(channelId: ChannelId) {
    setLiveChatDraft('')
    setSelectedChannel(channelId)
  }

  function sendComposer() {
    submitComposer({
      conversationId: selectedConversation.id,
      mode: composerMode,
      channelId: composerChannel,
      body: composerText,
      online,
      handoffTeam,
      handoffReason,
    })
    setComposerText('')
    setAttachmentReady(false)
  }

  function sendLiveChatReply(conversation: OmniConversation, channelId: ChannelId) {
    submitComposer({
      conversationId: conversation.id,
      mode: 'reply',
      channelId,
      body: liveChatDraft,
      online,
    })
    setLiveChatDraft('')
  }

  function renderNavItem(item: (typeof screenConfig)[number]) {
    const Icon = item.icon
    const active = state.selectedScreen === item.id
    return (
      <a
        key={item.id}
        className={`nav-item ${active ? 'active' : ''}`}
        href={routeHref({ screen: item.id })}
        onClick={(event) => handleAppLink(event, () => selectScreen(item.id))}
        title={item.label}
        aria-label={item.label}
        aria-current={active ? 'page' : undefined}
      >
        <Icon size={18} />
        <span>{item.label}</span>
      </a>
    )
  }

  function renderMetricCards() {
    const topPriorityConversation = prioritizedWork[0]?.conversation
    const firstBreachedConversation =
      prioritizedWork.find(({ conversation }) => conversation.slaState === 'breached')?.conversation ??
      state.conversations.find((conversation) => conversation.slaState === 'breached')
    const busiestChannel =
      [...state.channels].sort((a, b) => b.queueDepth + b.slaRisk - (a.queueDepth + a.slaRisk))[0]

    return (
      <section className="metric-grid" aria-label="Omnichannel metrics">
        {[
          {
            label: 'Needs attention',
            value: metrics.open,
            detail: `${metrics.atRisk} at risk`,
            cta: 'Open case list',
            href: routeHref({
              screen: 'inbox',
              channel: topPriorityConversation?.channelId,
              conversation: topPriorityConversation?.id,
              customer: topPriorityConversation?.customerId,
            }),
            action: () => openWorkQueueFocus({}, topPriorityConversation),
            icon: Inbox,
            tone: 'blue',
          },
          {
            label: 'Overdue promises',
            value: metrics.breached,
            detail: 'Manager action needed',
            cta: metrics.breached > 0 ? 'Open overdue case' : 'Open promise log',
            href: routeHref({
              screen: 'inbox',
              channel: firstBreachedConversation?.channelId,
              conversation: firstBreachedConversation?.id,
              customer: firstBreachedConversation?.customerId,
            }),
            action: () => openWorkQueueFocus({ sla: 'breached' }, firstBreachedConversation),
            icon: AlertTriangle,
            tone: 'red',
          },
          {
            label: 'Channels live',
            value: metrics.activeChannels,
            detail: `${metrics.avgHealth}% healthy`,
            cta: 'Open channel logs',
            href: routeHref({ screen: 'channels', channel: busiestChannel?.id }),
            action: () => {
              if (busiestChannel) setSelectedChannel(busiestChannel.id)
              else selectScreen('channels')
            },
            icon: Activity,
            tone: 'teal',
          },
          {
            label: 'Team load',
            value: `${metrics.avgOccupancy}%`,
            detail: `${metrics.csat} customer rating`,
            cta: 'Open staffing cases',
            href: routeHref({ screen: 'workforce' }),
            action: () => selectScreen('workforce'),
            icon: Gauge,
            tone: 'violet',
          },
          {
            label: 'Pending sends',
            value: metrics.outbox,
            detail: online ? 'All channels ready' : 'Will send when online',
            cta: 'Open send log',
            href: `${routeHref({ screen: 'admin' }).split('#')[0]}#outbound-queue`,
            action: () => selectScreen('admin'),
            icon: online ? Wifi : WifiOff,
            tone: 'amber',
          },
        ].map((metric) => {
          const Icon = metric.icon
          return (
            <a
              className={`metric-card tone-${metric.tone}`}
              href={metric.href}
              key={metric.label}
              onClick={(event) => handleAppLink(event, metric.action)}
              aria-label={`${metric.label}: ${metric.cta}`}
            >
              <div className="metric-icon">
                <Icon size={20} />
              </div>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <small>{metric.detail}</small>
              <em className="card-link-label">
                {metric.cta}
                <ArrowRight size={14} />
              </em>
            </a>
          )
        })}
      </section>
    )
  }

  function renderOperatingFlow() {
    const topPriorityConversation = prioritizedWork[0]?.conversation
    const firstRiskConversation =
      prioritizedWork.find(({ conversation }) => conversation.slaState !== 'healthy')?.conversation ??
      state.conversations.find((conversation) => conversation.slaState !== 'healthy')
    const activeHandoff = state.handoffs.find((handoff) => handoff.status !== 'completed')

    const steps = [
      {
        label: 'Spot risk',
        detail: 'See overdue promises, high queues, and customer mood before they escalate.',
        icon: Gauge,
        href: routeHref({
          screen: 'inbox',
          channel: firstRiskConversation?.channelId,
          conversation: firstRiskConversation?.id,
          customer: firstRiskConversation?.customerId,
        }),
        action: () =>
          openWorkQueueFocus(
            firstRiskConversation ? { sla: firstRiskConversation.slaState } : { sla: 'risk' },
            firstRiskConversation,
          ),
      },
      {
        label: 'Work one queue',
        detail: 'Open the customer thread with owner, history, answer, and next action together.',
        icon: Inbox,
        href: routeHref({
          screen: 'inbox',
          channel: topPriorityConversation?.channelId,
          conversation: topPriorityConversation?.id,
          customer: topPriorityConversation?.customerId,
        }),
        action: () => openWorkQueueFocus({}, topPriorityConversation),
      },
      {
        label: 'Use native chats',
        detail: 'Handle WhatsApp, Instagram, and Facebook in dedicated chat windows.',
        icon: MessageCircle,
        href: routeHref({ screen: 'channels', channel: 'whatsapp' }),
        action: () => openDirectChannel('whatsapp'),
      },
      {
        label: 'Close the loop',
        detail: 'Move cross-team work with owner, due time, checklist, and customer update.',
        icon: Handshake,
        href: activeHandoff
          ? routeHref({
              screen: 'handoffs',
              conversation: activeHandoff.conversationId,
              customer: activeHandoff.customerId,
            })
          : routeHref({ screen: 'handoffs' }),
        action: () => selectScreen('handoffs'),
      },
    ]

    return (
      <section className="flow-strip" aria-label="Operating flow">
        {steps.map((step, index) => {
          const Icon = step.icon
          return (
            <a
              className="flow-card"
              href={step.href}
              onClick={(event) => handleAppLink(event, step.action)}
              key={step.label}
            >
              <span className="flow-index">{index + 1}</span>
              <Icon size={18} />
              <strong>{step.label}</strong>
              <small>{step.detail}</small>
            </a>
          )
        })}
      </section>
    )
  }

  function renderPriorityWork() {
    return (
      <div className="panel priority-work-panel">
        <div className="panel-head">
          <div>
            <span>Start here</span>
            <h2>Priority work queue</h2>
          </div>
          <ClipboardList size={20} />
        </div>
        <div className="priority-work-list">
          {prioritizedWork.map(({ conversation, customer, channel, owner, score }) => {
            const ChannelIcon = channelIcons[conversation.channelId]
            return (
              <a
                className={`priority-work-row sla-${conversation.slaState}`}
                href={routeHref({
                  screen: 'inbox',
                  channel: conversation.channelId,
                  conversation: conversation.id,
                  customer: conversation.customerId,
                })}
                key={conversation.id}
                onClick={(event) => handleAppLink(event, () => openConversationInInbox(conversation))}
              >
                <div className="priority-score">
                  <strong>{score}</strong>
                  <span>risk</span>
                </div>
                <div className="priority-work-main">
                  <div className="row-topline">
                    <span>{conversation.ticketNumber}</span>
                    <span>
                      <ChannelIcon size={13} />
                      {channel?.label}
                    </span>
                    <span>{slaLabels[conversation.slaState]}</span>
                  </div>
                  <strong>{conversation.subject}</strong>
                  <small>{customer?.name} · {promiseLabel(conversation)}</small>
                </div>
                <div className="priority-work-owner">
                  <span>{owner?.name}</span>
                  <small>{channelWorkMode(conversation.channelId)}</small>
                </div>
                <ArrowRight size={16} />
              </a>
            )
          })}
        </div>
      </div>
    )
  }

  function renderCommand() {
    return (
      <div className="screen-stack">
        {renderOperatingFlow()}
        {renderMetricCards()}

        <section className="command-grid">
          <div className="command-column command-primary">
            {renderPriorityWork()}
            <div className="panel command-queue">
              <div className="panel-head">
                <div>
                  <span>Today&apos;s demand</span>
                  <h2>Channel health and queue load</h2>
                </div>
                <button
                  className="icon-button"
                  type="button"
                  aria-label="Refresh channel board"
                  onClick={() => announcePrototype('Channel board refreshed with the latest workspace data.')}
                >
                  <RefreshCw size={17} />
                </button>
              </div>
              <div className="channel-grid">
                {channelTotals.map(({ channel, conversations }) => {
                  const Icon = channelIcons[channel.id]
                  return (
                    <a
                      className={`channel-card ${channel.status}`}
                      key={channel.id}
                      href={routeHref({ screen: 'channels', channel: channel.id })}
                      onClick={(event) => handleAppLink(event, () => setSelectedChannel(channel.id))}
                      aria-label={`Open ${channel.label} channel workspace`}
                    >
                      <div className="channel-top">
                        <span className="channel-icon">
                          <Icon size={18} />
                        </span>
                        <span className={`status-dot ${channel.status}`}>{titleCase(channel.status)}</span>
                      </div>
                      <strong>{channel.label}</strong>
                      <small>{channel.description}</small>
                      <div className="channel-metrics">
                        <span>
                          <b>{channel.queueDepth}</b>
                          waiting
                        </span>
                        <span>
                          <b>{channel.activeSessions}</b>
                          in work
                        </span>
                        <span>
                          <b>{channel.slaRisk}</b>
                          at risk
                        </span>
                      </div>
                      <div className="health-track">
                        <span style={{ width: `${channel.health}%` }} />
                      </div>
                      <em>{conversations.length} open {queueNoun(conversations.length)} in this channel</em>
                      <span className="card-link-label">
                        Open {channel.shortLabel} log
                        <ArrowRight size={14} />
                      </span>
                    </a>
                  )
                })}
              </div>
            </div>

            <div className="panel command-actions">
              <div className="panel-head">
                <div>
                  <span>Manager actions</span>
                  <h2>Decide next</h2>
                </div>
                <Timer size={20} />
              </div>
              <div className="action-list">
                {[
                  {
                    label: 'Move 4 chat conversations from Noah to Amara before Noah reaches capacity.',
                    href: routeHref({ screen: 'workforce' }),
                    action: () => selectScreen('workforce'),
                  },
                  {
                    label: 'Restart fulfillment handoffs once the receiving team confirms capacity.',
                    href: routeHref({ screen: 'handoffs' }),
                    action: () => selectScreen('handoffs'),
                  },
                  {
                    label: 'Escalate OMNI-1004 because the public social response is overdue.',
                    href: routeHref({
                      screen: 'inbox',
                      conversation: state.conversations.find((item) => item.ticketNumber === 'OMNI-1004')?.id,
                    }),
                    action: () => {
                      const conversation = state.conversations.find((item) => item.ticketNumber === 'OMNI-1004')
                      if (conversation) openConversationInInbox(conversation)
                    },
                  },
                  {
                    label: 'Approve the social complaint answer so agents can respond consistently.',
                    href: routeHref({ screen: 'knowledge' }),
                    action: () => selectScreen('knowledge'),
                  },
                ].map((action) => (
                  <a
                    className="action-row"
                    href={action.href}
                    key={action.label}
                    onClick={(event) => handleAppLink(event, action.action)}
                  >
                    <CheckCircle2 size={17} />
                    <span>{action.label}</span>
                  </a>
                ))}
              </div>
            </div>
          </div>

          <div className="command-column command-secondary">
            <div className="panel command-alerts">
              <div className="panel-head">
                <div>
                  <span>Service alerts</span>
                  <h2>What needs attention</h2>
                </div>
                <Bot size={20} />
              </div>
              <div className="ai-alerts">
                {state.conversations
                  .filter((conversation) => conversation.slaState !== 'healthy')
                  .map((conversation) => (
                    <a
                      className="ai-alert"
                      key={conversation.id}
                      href={routeHref({
                        screen: 'inbox',
                        conversation: conversation.id,
                        customer: conversation.customerId,
                      })}
                      onClick={(event) => handleAppLink(event, () => openConversationInInbox(conversation))}
                      aria-label={`Open ${conversation.ticketNumber} in unified inbox`}
                    >
                      <Sparkles size={17} />
                      <span>
                        <strong>{conversation.ticketNumber}</strong>
                        <small>{conversation.copilot.slaReason}</small>
                      </span>
                      <ArrowRight size={16} />
                    </a>
                  ))}
                <a
                  className="ai-alert soft"
                  href={routeHref({ screen: 'knowledge' })}
                  onClick={(event) => handleAppLink(event, () => selectScreen('knowledge'))}
                  aria-label="Open Knowledge to review article gap"
                >
                  <BookOpen size={17} />
                  <span>
                    <strong>Missing answer</strong>
                    <small>Social complaint guidance is still in review while public volume is rising.</small>
                  </span>
                </a>
              </div>
            </div>

            <div className="panel command-workforce">
              <div className="panel-head">
                <div>
                  <span>Staffing</span>
                  <h2>Availability and load</h2>
                </div>
                <Users size={20} />
              </div>
              <div className="agent-grid">
                {state.agents.map((agent) => (
                  <a
                    className="agent-card"
                    href={routeHref({ screen: 'inbox' })}
                    key={agent.id}
                    onClick={(event) =>
                      handleAppLink(event, () => openWorkQueueFocus({ assignee: agent.id }))
                    }
                    aria-label={`Open active cases assigned to ${agent.name}`}
                  >
                    <div className="avatar">{agent.avatar}</div>
                    <div>
                      <strong>{agent.name}</strong>
                      <span>{agent.role}</span>
                      <div className="skill-row">
                        {agent.skills.slice(0, 3).map((skill) => (
                          <small key={skill}>{skill}</small>
                        ))}
                      </div>
                    </div>
                    <div className="agent-load">
                      <b>{agent.occupancy}%</b>
                      <span className={`availability ${agent.availability}`}>
                        {titleCase(agent.availability)}
                      </span>
                    </div>
                    <span className="card-link-label">
                      Open assigned cases
                      <ArrowRight size={14} />
                    </span>
                  </a>
                ))}
              </div>
            </div>
          </div>
        </section>
      </div>
    )
  }

  function renderFilters() {
    return (
      <aside className="filter-panel">
        <div className="panel-head compact">
          <div>
            <span>Focus</span>
            <h2>Work Queue</h2>
          </div>
          <Filter size={18} />
        </div>

        <div className="quick-queues">
          {[
            ['All open', 'all'],
            ['At risk', 'risk'],
            ['Overdue', 'breached'],
            ['Urgent', 'urgent'],
          ].map(([label, value]) => (
            <button
              type="button"
              key={label}
              aria-pressed={
                value === 'all'
                  ? state.filters.channel === 'all' &&
                    state.filters.sla === 'all' &&
                    state.filters.priority === 'all'
                  : value === 'urgent'
                    ? state.filters.priority === 'urgent'
                    : state.filters.sla === value
              }
              onClick={() => {
                if (value === 'all') resetFilters()
                if (value === 'risk') setFilters({ sla: 'risk' })
                if (value === 'breached') setFilters({ sla: 'breached' })
                if (value === 'urgent') setFilters({ priority: 'urgent' })
              }}
            >
              <span>{label}</span>
              <strong>
                {value === 'all'
                  ? state.conversations.length
                  : value === 'urgent'
                    ? state.conversations.filter((item) => item.priority === 'urgent').length
                    : state.conversations.filter((item) => item.slaState === value).length}
              </strong>
            </button>
          ))}
        </div>

        <label>
          Channel
          <select
            value={state.filters.channel}
            onChange={(event) => setFilters({ channel: event.target.value as ChannelId | 'all' })}
          >
            <option value="all">All channels</option>
            {state.channels.map((channel) => (
              <option value={channel.id} key={channel.id}>
                {channel.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Promise time
          <select
            value={state.filters.sla}
            onChange={(event) => setFilters({ sla: event.target.value as SlaState | 'all' })}
          >
            {slaOptions.map((option) => (
              <option value={option} key={option}>
                {option === 'all' ? 'All promise states' : slaLabels[option]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Priority
          <select
            value={state.filters.priority}
            onChange={(event) => setFilters({ priority: event.target.value as Priority | 'all' })}
          >
            {priorityOptions.map((option) => (
              <option value={option} key={option}>
                {option === 'all' ? 'All priorities' : titleCase(option)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select
            value={state.filters.status}
            onChange={(event) => setFilters({ status: event.target.value as ConversationStatus | 'all' })}
          >
            {statusOptions.map((option) => (
              <option value={option} key={option}>
                {option === 'all' ? 'All statuses' : titleCase(option)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Customer mood
          <select
            value={state.filters.sentiment}
            onChange={(event) => setFilters({ sentiment: event.target.value as Sentiment | 'all' })}
          >
            {sentimentOptions.map((option) => (
              <option value={option} key={option}>
                {option === 'all' ? 'All moods' : sentimentLabels[option]}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary-action" type="button" onClick={resetFilters}>
          <RotateCcw size={16} />
          Clear filters
        </button>
      </aside>
    )
  }

  function renderConversationRow(conversation: OmniConversation) {
    const channel = state.channels.find((item) => item.id === conversation.channelId)
    const customer = state.customers.find((item) => item.id === conversation.customerId)
    const agent = state.agents.find((item) => item.id === conversation.assigneeId)
    const Icon = channelIcons[conversation.channelId]
    return (
      <a
        className={`conversation-row ${selectedConversation.id === conversation.id ? 'active' : ''}`}
        key={conversation.id}
        href={routeHref({
          screen: 'inbox',
          conversation: conversation.id,
          customer: conversation.customerId,
        })}
        onClick={(event) => handleAppLink(event, () => openConversation(conversation))}
        aria-current={selectedConversation.id === conversation.id ? 'true' : undefined}
        aria-label={`Open ${conversation.ticketNumber}: ${conversation.subject}`}
      >
        <div className="row-main">
          <div className="row-icon">
            <Icon size={18} />
          </div>
          <div>
            <div className="row-topline">
              <strong>{conversation.ticketNumber}</strong>
              <span>{channel?.shortLabel}</span>
              {conversation.unread && <em>Unread</em>}
            </div>
            <h3>{conversation.subject}</h3>
            <p>{conversation.preview}</p>
            <div className="row-meta">
              <span>{customer?.name}</span>
              <span>{agent?.name}</span>
              <span>{conversation.intent}</span>
            </div>
          </div>
        </div>
        <div className="row-badges">
          <span className={`chip priority-${conversation.priority}`}>{titleCase(conversation.priority)}</span>
          <span className={`chip sla-${conversation.slaState}`}>{slaLabels[conversation.slaState]}</span>
          <span className={`chip sentiment-${conversation.sentiment}`}>
            {sentimentLabels[conversation.sentiment]}
          </span>
        </div>
      </a>
    )
  }

  function renderCustomer360() {
    const profileContactMethods = selectedCustomer.contactMethods.filter(
      (method) => method.type !== 'whatsapp' && method.type !== 'social',
    )

    return (
      <aside className="customer-360">
        <div className="panel-head compact">
          <div>
            <span>Customer 360</span>
            <h2>{selectedCustomer.name}</h2>
          </div>
          <Building2 size={18} />
        </div>
        <div className="customer-score">
          <strong>{selectedCustomer.healthScore}</strong>
          <span>Health score</span>
          <div className="health-track">
            <span style={{ width: `${selectedCustomer.healthScore}%` }} />
          </div>
        </div>
        <div className="profile-lines">
          <span>{selectedCustomer.company}</span>
            <span>{selectedCustomer.title}</span>
            <span>{selectedCustomer.location}</span>
          <span>{selectedCustomer.openValue} open customer value</span>
        </div>
        <div className="contact-list">
          {profileContactMethods.map((method) => (
            <a
              className="contact-link"
              href={contactHref(method, selectedCustomer.id)}
              key={`${method.type}-${method.value}`}
              onClick={
                method.type === 'portal'
                  ? (event) =>
                      handleAppLink(event, () => {
                        setSelectedChannel('portal')
                        announcePrototype(`${selectedCustomer.name}'s portal workspace opened.`)
                      })
                  : undefined
              }
              aria-label={`${method.label}: ${method.value}`}
            >
              <strong>{method.label}</strong>
              <span>{method.value}</span>
            </a>
          ))}
        </div>
        <div className="tag-list">
          {selectedCustomer.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
        <p className="recent-activity">{selectedCustomer.recentActivity}</p>
      </aside>
    )
  }

  function renderConversationDetail() {
    const ChannelIcon = channelIcons[selectedConversation.channelId]
    const channelWorkspaceHref = routeHref({
      screen: 'channels',
      channel: selectedConversation.channelId,
      conversation: selectedConversation.id,
      customer: selectedConversation.customerId,
    })
    const agentReplySent = selectedConversation.timeline.some(
      (event) => event.authorRole === 'agent' && event.type === 'agent-reply',
    )
    const completedTasks = selectedConversation.tasks.filter((task) => task.done).length
    const taskProgress = percent(completedTasks, selectedConversation.tasks.length)
    const planSteps = [
      {
        label: 'Acknowledge customer',
        detail: `${agentReplySent ? 'Reply already sent' : `Respond through ${selectedChannel.label}`} and keep the same thread moving.`,
        state: agentReplySent ? 'done' : 'next',
      },
      {
        label: 'Clear blocker',
        detail:
          selectedHandoffs.length > 0
            ? `${selectedHandoffs[0].receivingTeam} owns the active handoff.`
            : selectedConversation.copilot.recommendedAction,
        state: selectedHandoffs.length > 0 ? 'blocked' : 'next',
      },
      {
        label: 'Close promise',
        detail: `${taskProgress}% of checklist complete. ${promiseLabel(selectedConversation)}.`,
        state: selectedConversation.slaState === 'breached' ? 'urgent' : 'next',
      },
    ]

    return (
      <section className="conversation-detail">
        <div className="detail-header">
          <div>
            <div className="eyebrow-row">
              <span>{selectedConversation.ticketNumber}</span>
              <span>
                <ChannelIcon size={14} />
                {selectedChannel.label}
              </span>
              <span>{selectedConversation.intent}</span>
            </div>
            <h2>{selectedConversation.subject}</h2>
            <p>{selectedConversation.preview}</p>
          </div>
          <div className="detail-actions">
            <button
              className="icon-button"
              type="button"
              aria-label="Raise priority"
              onClick={() => updateConversation(selectedConversation.id, { priority: 'urgent' })}
            >
              <AlertTriangle size={17} />
            </button>
            <button
              className="primary-action"
              type="button"
              onClick={() => updateConversation(selectedConversation.id, { status: 'resolved', slaState: 'healthy' })}
            >
              <Check size={17} />
              Resolve
            </button>
          </div>
        </div>

        <div className="ticket-command-strip" aria-label="Ticket operating signals">
          <div>
            <span>Promise</span>
            <strong className={`sla-text ${selectedConversation.slaState}`}>
              {promiseLabel(selectedConversation)}
            </strong>
          </div>
          <div>
            <span>Customer mood</span>
            <strong>{sentimentLabels[selectedConversation.sentiment]}</strong>
          </div>
          <div>
            <span>Owner load</span>
            <strong>{selectedAgent ? `${selectedAgent.occupancy}% · ${selectedAgent.availability}` : 'Unassigned'}</strong>
          </div>
          <div>
            <span>Customer scope</span>
            <strong>{selectedCustomerOpenWork.length} open item(s)</strong>
          </div>
          <a
            className="primary-action"
            href={channelWorkspaceHref}
            onClick={(event) =>
              handleAppLink(event, () => {
                setSelectedChannel(selectedConversation.channelId)
                selectScreen('channels')
              })
            }
          >
            <ChannelIcon size={16} />
            {isDirectMessageChannel(selectedConversation.channelId)
              ? `Open ${selectedChannel.label} chat`
              : `Open ${selectedChannel.label} queue`}
          </a>
        </div>

        <div className="detail-layout">
          <div className="timeline-column">
            <article className="copilot-card">
              <div className="copilot-head">
                <span>
                  <Bot size={18} />
                  Agent assist
                </span>
                <strong>{selectedConversation.copilot.confidence}% match</strong>
              </div>
              <p>{selectedConversation.copilot.summary}</p>
              <div className="copilot-grid">
                <div>
                  <span>Customer mood</span>
                  <strong>{sentimentLabels[selectedConversation.copilot.sentiment]}</strong>
                </div>
                <div>
                  <span>Best answer</span>
                  <strong>{selectedConversation.copilot.suggestedArticle}</strong>
                </div>
                <div>
                  <span>Next decision</span>
                  <strong>{selectedConversation.copilot.escalation}</strong>
                </div>
              </div>
            </article>

            <article className="resolution-plan">
              <div className="panel-head compact">
                <div>
                  <span>Execution plan</span>
                  <h2>Next best path</h2>
                </div>
                <CheckCircle2 size={18} />
              </div>
              <div className="resolution-steps">
                {planSteps.map((step, index) => (
                  <div className={`resolution-step ${step.state}`} key={step.label}>
                    <span>{index + 1}</span>
                    <div>
                      <strong>{step.label}</strong>
                      <small>{step.detail}</small>
                    </div>
                  </div>
                ))}
              </div>
            </article>

            <div className="timeline">
              {selectedConversation.timeline.map((event) => {
                const EventIcon = channelIcons[event.channelId]
                return (
                  <article className={`timeline-event ${event.type}`} key={event.id}>
                    <div className="timeline-icon">
                      <EventIcon size={16} />
                    </div>
                    <div>
                      <div className="timeline-top">
                        <strong>{event.author}</strong>
                        <span>{titleCase(event.type)}</span>
                        <small>{formatTime(event.timestamp)}</small>
                      </div>
                      <p>{event.body}</p>
                      {event.deliveryState && (
                        <em className={`delivery-state ${event.deliveryState}`}>
                          {deliveryLabel(event.deliveryState)}
                        </em>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>

            <article className="composer">
              <div className="composer-toolbar">
                <div className="segmented" role="group" aria-label="Composer mode">
                  {(['reply', 'note', 'handoff'] as ComposerMode[]).map((mode) => (
                    <button
                      type="button"
                      key={mode}
                      className={composerMode === mode ? 'active' : ''}
                      aria-pressed={composerMode === mode}
                      onClick={() => setComposerMode(mode)}
                    >
                      {composerModeLabels[mode]}
                    </button>
                  ))}
                </div>
                <select
                  value={composerChannel}
                  onChange={(event) => setComposerChannel(event.target.value as ChannelId)}
                  aria-label="Reply channel"
                >
                  {state.channels.map((channel) => (
                    <option value={channel.id} key={channel.id}>
                      {channel.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="composer-tools">
                <select
                  value=""
                  onChange={(event) => {
                    setComposerText(event.target.value)
                    event.currentTarget.value = ''
                  }}
                  aria-label="Macro"
                >
                  <option value="">Insert macro</option>
                  {macros.map((macro) => (
                    <option value={macro} key={macro}>
                      {macro.slice(0, 58)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className={translationOn ? 'tool-toggle active' : 'tool-toggle'}
                  aria-pressed={translationOn}
                  onClick={() => setTranslationOn((value) => !value)}
                >
                  <Languages size={16} />
                  Translate
                </button>
                <button
                  type="button"
                  className={attachmentReady ? 'tool-toggle active' : 'tool-toggle'}
                  aria-pressed={attachmentReady}
                  onClick={() => setAttachmentReady((value) => !value)}
                >
                  <Paperclip size={16} />
                  {attachmentReady ? 'Attached' : 'Attach'}
                </button>
              </div>
              {attachmentReady && (
                <div className="attachment-strip">
                  <Paperclip size={15} />
                  <span>Customer screenshot.pdf ready to include</span>
                  <button type="button" onClick={() => setAttachmentReady(false)}>
                    Remove
                  </button>
                </div>
              )}
              {composerMode === 'handoff' && (
                <div className="handoff-composer-fields">
                  <label>
                    Receiving team
                    <select
                      value={handoffTeam}
                      onChange={(event) => setHandoffTeam(event.target.value)}
                    >
                      {handoffTeams.map((team) => (
                        <option value={team} key={team}>
                          {team}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Handoff reason
                    <input
                      value={handoffReason}
                      onChange={(event) => setHandoffReason(event.target.value)}
                      placeholder="Why this team must take action"
                    />
                  </label>
                </div>
              )}
              <textarea
                value={composerText}
                onChange={(event) => setComposerText(event.target.value)}
                placeholder={
                  composerMode === 'reply'
                    ? 'Write a public reply across the selected channel'
                    : composerMode === 'note'
                      ? 'Add an internal note for the team'
                      : 'Tell the receiving team what to own and when to respond'
                }
              />
              <div className="suggested-reply">
                <Sparkles size={16} />
                <button
                  type="button"
                  onClick={() => setComposerText(selectedConversation.copilot.suggestedReply)}
                  aria-label="Use suggested reply"
                >
                  Use suggested reply
                </button>
                <span>{selectedConversation.copilot.recommendedAction}</span>
              </div>
              <div className="composer-footer">
                <span>{online ? 'Ready to send' : 'Offline: will send when connection returns'}</span>
                <button
                  className="primary-action"
                  type="button"
                  onClick={sendComposer}
                  disabled={!composerText.trim()}
                >
                  <Send size={17} />
                  {online ? 'Send update' : 'Queue update'}
                </button>
              </div>
            </article>
          </div>

          <aside className="properties-panel">
            <label>
              Status
              <select
                value={selectedConversation.status}
                onChange={(event) =>
                  updateConversation(selectedConversation.id, {
                    status: event.target.value as ConversationStatus,
                  })
                }
              >
                {statusOptions
                  .filter((option) => option !== 'all')
                  .map((option) => (
                    <option value={option} key={option}>
                      {titleCase(option)}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Priority
              <select
                value={selectedConversation.priority}
                onChange={(event) =>
                  updateConversation(selectedConversation.id, { priority: event.target.value as Priority })
                }
              >
                {priorityOptions
                  .filter((option) => option !== 'all')
                  .map((option) => (
                    <option value={option} key={option}>
                      {titleCase(option)}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Assignee
              <select
                value={selectedConversation.assigneeId}
                onChange={(event) =>
                  updateConversation(selectedConversation.id, { assigneeId: event.target.value })
                }
              >
                {state.agents.map((agent) => (
                  <option value={agent.id} key={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="property-card">
              <span>Promise time</span>
              <strong className={`sla-text ${selectedConversation.slaState}`}>
                {slaLabels[selectedConversation.slaState]}
              </strong>
              <small>First response {formatTime(selectedConversation.firstResponseDue)}</small>
              <small>Resolution {formatTime(selectedConversation.resolutionDue)}</small>
            </div>
            <div className="property-card">
              <span>Labels</span>
              <div className="tag-list">
                {selectedConversation.tags.map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
            </div>
            <div className="property-card">
              <span>Tasks</span>
              <div className="task-list">
                {selectedConversation.tasks.map((task) => (
                  <label key={task.id}>
                    <input
                      type="checkbox"
                      checked={task.done}
                      onChange={() => toggleTask(selectedConversation.id, task.id)}
                    />
                    {task.label}
                  </label>
                ))}
              </div>
            </div>
            <div className="property-card">
              <span>Agent owner</span>
              <strong>{selectedAgent?.name}</strong>
              <small>{selectedAgent?.role}</small>
            </div>
          </aside>
        </div>
      </section>
    )
  }

  function renderInbox() {
    return (
      <div className="inbox-layout">
        {renderFilters()}
        <section className="conversation-list-panel">
          <div className="search-row">
            <Search size={16} />
            <input
              value={state.filters.search}
              onChange={(event) => setFilters({ search: event.target.value })}
              placeholder="Search customer, ticket, topic, or label"
              aria-label="Search conversations"
            />
            <button
              className="icon-button"
              type="button"
              aria-label="New ticket"
              onClick={() => openQuickCreate(state.filters.channel === 'all' ? 'email' : state.filters.channel)}
            >
              <Plus size={17} />
            </button>
          </div>
          <div className="conversation-list">
            {filteredConversations.length > 0 ? (
              filteredConversations.map((conversation) => renderConversationRow(conversation))
            ) : (
              <div className="empty-state compact">
                <strong>No work matches these filters</strong>
                <span>Clear filters or search another customer, topic, or label.</span>
                <button className="secondary-action" type="button" onClick={resetFilters}>
                  Clear filters
                </button>
              </div>
            )}
          </div>
        </section>
        <div className="inbox-detail-stack">
          {renderConversationDetail()}
          {renderCustomer360()}
        </div>
      </div>
    )
  }

  function renderQuickCreatePanel() {
    if (!quickCreateOpen) return null

    return (
      <div className="modal-backdrop" role="presentation" onMouseDown={() => setQuickCreateOpen(false)}>
        <section
          className="quick-create-panel"
          role="dialog"
          aria-modal="true"
          aria-labelledby="quick-create-title"
          onMouseDown={(event) => event.stopPropagation()}
        >
          <div className="panel-head">
            <div>
              <span>New work item</span>
              <h2 id="quick-create-title">Create ticket</h2>
            </div>
            <button className="icon-button" type="button" aria-label="Close new ticket" onClick={() => setQuickCreateOpen(false)}>
              <X size={17} />
            </button>
          </div>
          <form
            className="quick-create-form"
            onSubmit={(event) => {
              event.preventDefault()
              submitQuickTicket()
            }}
          >
            <label>
              Customer
              <select
                value={quickTicket.customerId}
                onChange={(event) => updateQuickTicket({ customerId: event.target.value })}
              >
                {state.customers.map((customer) => (
                  <option value={customer.id} key={customer.id}>
                    {customer.name} · {customer.company}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Channel
              <select
                value={quickTicket.channelId}
                onChange={(event) => updateQuickTicket({ channelId: event.target.value as ChannelId })}
              >
                {state.channels.map((channel) => (
                  <option value={channel.id} key={channel.id}>
                    {channel.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Priority
              <select
                value={quickTicket.priority}
                onChange={(event) => updateQuickTicket({ priority: event.target.value as Priority })}
              >
                {priorityOptions
                  .filter((option) => option !== 'all')
                  .map((option) => (
                    <option value={option} key={option}>
                      {titleCase(option)}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Owner
              <select
                value={quickTicket.assigneeId}
                onChange={(event) => updateQuickTicket({ assigneeId: event.target.value })}
              >
                {state.agents.map((agent) => (
                  <option value={agent.id} key={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="span-all">
              Subject
              <input
                value={quickTicket.subject}
                onChange={(event) => updateQuickTicket({ subject: event.target.value })}
                placeholder="Short customer issue"
              />
            </label>
            <label className="span-all">
              Customer message
              <textarea
                value={quickTicket.body}
                onChange={(event) => updateQuickTicket({ body: event.target.value })}
                placeholder="What the customer needs help with"
              />
            </label>
            <div className="quick-create-footer">
              <span>Creates a ticket, opens it in Work Queue, and updates the selected channel count.</span>
              <button className="primary-action" type="submit" disabled={!quickTicket.subject.trim() || !quickTicket.body.trim()}>
                <Plus size={16} />
                Create ticket
              </button>
            </div>
          </form>
        </section>
      </div>
    )
  }

  function renderNotificationPanel() {
    if (!notificationOpen) return null

    return (
      <section className="notification-panel" aria-label="Notifications">
        <div className="panel-head compact">
          <div>
            <span>Needs attention</span>
            <h2>Notifications</h2>
          </div>
          <button className="icon-button" type="button" aria-label="Close notifications" onClick={() => setNotificationOpen(false)}>
            <X size={16} />
          </button>
        </div>
        <div className="notification-list">
          {serviceNotifications.map((item) => (
            <a
              className="notification-item"
              href={item.href}
              key={item.id}
              onClick={(event) =>
                handleAppLink(event, () => {
                  setNotificationOpen(false)
                  item.action()
                })
              }
            >
              <AlertTriangle size={15} />
              <span>
                <strong>{item.title}</strong>
                <small>{item.body}</small>
              </span>
              <span className="notification-action">
                Open
                <ArrowRight size={14} />
              </span>
            </a>
          ))}
        </div>
      </section>
    )
  }

  function renderChannelOverview(channel: (typeof state.channels)[number]) {
    const Icon = channelIcons[channel.id]
    const conversations = state.conversations
      .filter((conversation) => conversation.channelId === channel.id)
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())

    return (
      <section className="panel channel-overview-panel">
        <div className="panel-head">
          <div>
            <span>Focused channel</span>
            <h2>{channel.label} queue</h2>
          </div>
          <Icon size={20} />
        </div>

        <div className="channel-overview-metrics">
          <div>
            <strong>{channel.queueDepth}</strong>
            <span>waiting</span>
          </div>
          <div>
            <strong>{channel.avgWaitMinutes}m</strong>
            <span>avg wait</span>
          </div>
          <div>
            <strong>{channel.health}%</strong>
            <span>healthy</span>
          </div>
        </div>

        <p className="panel-copy">{channel.description}</p>

        <div className="mini-ticket-list" aria-label={`${channel.label} tickets`}>
          {conversations.length > 0 ? (
            conversations.map((conversation) => {
              const customer = state.customers.find((item) => item.id === conversation.customerId)
              return (
                <a
                  href={routeHref({
                    screen: 'inbox',
                    channel: channel.id,
                    conversation: conversation.id,
                    customer: conversation.customerId,
                  })}
                  key={conversation.id}
                  onClick={(event) => handleAppLink(event, () => openConversationInInbox(conversation))}
                >
                  <span>
                    <strong>{conversation.ticketNumber}</strong>
                    <small>{customer?.name} · {conversation.subject}</small>
                  </span>
                  <em className={`chip sla-${conversation.slaState}`}>{slaLabels[conversation.slaState]}</em>
                </a>
              )
            })
          ) : (
            <div className="empty-state compact">
              <strong>No open work in {channel.label}</strong>
              <span>New customer items will appear here as soon as they arrive.</span>
            </div>
          )}
        </div>

        <div className="channel-overview-actions">
          <button
            className="secondary-action"
            type="button"
            aria-pressed={channel.intakeEnabled}
            onClick={() => toggleChannelIntake(channel.id)}
          >
            {channel.intakeEnabled ? 'Pause intake' : 'Resume intake'}
          </button>
          <a
            className="primary-action"
            href={routeHref({ screen: 'inbox', channel: channel.id })}
            onClick={(event) =>
              handleAppLink(event, () => {
                setFilters({ channel: channel.id })
                selectScreen('inbox')
              })
            }
          >
            Open in Work Queue
          </a>
        </div>
      </section>
    )
  }

  function renderDirectChannelChat() {
    const activeChannel =
      state.channels.find((channel) => channel.id === activeDirectChannelId) ??
      state.channels.find((channel) => channel.id === 'whatsapp') ??
      state.channels[0]
    const ActiveIcon = channelIcons[activeDirectChannelId]
    const channelConversations = state.conversations
      .filter((conversation) => conversation.channelId === activeDirectChannelId)
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    const liveConversation =
      channelConversations.find((conversation) => conversation.id === selectedConversation.id) ??
      channelConversations[0]
    const liveCustomer = state.customers.find((customer) => customer.id === liveConversation?.customerId)
    const liveAgent = state.agents.find((agent) => agent.id === liveConversation?.assigneeId)
    const channelEvents =
      liveConversation?.timeline.filter(
        (event) => event.channelId === activeDirectChannelId || event.type === 'automation',
      ) ?? []

    return (
      <section className="panel direct-chat-panel">
        <div className="panel-head">
          <div>
            <span>Customer messaging</span>
            <h2>{activeChannel.label} conversations</h2>
          </div>
          <ActiveIcon size={20} />
        </div>

        <div className="direct-channel-tabs" role="tablist" aria-label="Direct message channels">
          {directMessageChannelIds.map((channelId) => {
            const channel = state.channels.find((item) => item.id === channelId)
            const Icon = channelIcons[channelId]
            const openCount = state.conversations.filter(
              (conversation) =>
                conversation.channelId === channelId && conversation.status !== 'resolved',
            ).length

            return (
              <a
                className={channelId === activeDirectChannelId ? 'active' : ''}
                key={channelId}
                href={routeHref({ screen: 'channels', channel: channelId })}
                onClick={(event) => handleAppLink(event, () => openDirectChannel(channelId))}
                role="tab"
                aria-selected={channelId === activeDirectChannelId}
                aria-controls="direct-chat-window"
              >
                <Icon size={16} />
                <span>{channel?.label}</span>
                <b>{openCount}</b>
              </a>
            )
          })}
        </div>

        <div className="direct-chat-layout">
          <div className="direct-thread-list" aria-label={`${activeChannel.label} conversations`}>
            {channelConversations.map((conversation) => {
              const customer = state.customers.find((item) => item.id === conversation.customerId)
              return (
                <a
                  className={liveConversation?.id === conversation.id ? 'active' : ''}
                  key={conversation.id}
                  href={routeHref({
                    screen: 'channels',
                    channel: activeDirectChannelId,
                    conversation: conversation.id,
                    customer: conversation.customerId,
                  })}
                  onClick={(event) =>
                    handleAppLink(event, () => {
                      setLiveChatDraft('')
                      openConversation(conversation)
                    })
                  }
                  aria-current={liveConversation?.id === conversation.id ? 'true' : undefined}
                  aria-label={`Open ${conversation.ticketNumber} ${activeChannel.label} chat`}
                >
                  <span>
                    <strong>{conversation.ticketNumber}</strong>
                    <small>{customer?.name}</small>
                  </span>
                  <em className={`chip sla-${conversation.slaState}`}>
                    {slaLabels[conversation.slaState]}
                  </em>
                </a>
              )
            })}
          </div>

          <div className="direct-chat-window" id="direct-chat-window">
            {liveConversation ? (
              <>
                <div className="direct-chat-head">
                  <span className="channel-icon">
                    <ActiveIcon size={18} />
                  </span>
                  <div>
                    <strong>{liveCustomer?.name}</strong>
                    <small>
                      {liveConversation.subject} · {liveAgent?.name}
                    </small>
                  </div>
                  <span className={`chip priority-${liveConversation.priority}`}>
                    {titleCase(liveConversation.priority)}
                  </span>
                </div>

                <div className="direct-chat-messages">
                  {channelEvents.map((event) => (
                    <article className={`direct-message ${event.authorRole}`} key={event.id}>
                      <div>
                        <strong>{event.author}</strong>
                        <small>{formatTime(event.timestamp)}</small>
                      </div>
                      <p>{event.body}</p>
                      {event.deliveryState && (
                        <em className={`delivery-state ${event.deliveryState}`}>
                          {deliveryLabel(event.deliveryState)}
                        </em>
                      )}
                    </article>
                  ))}
                </div>

                <div className="direct-chat-composer">
                  <textarea
                    value={liveChatDraft}
                    onChange={(event) => setLiveChatDraft(event.target.value)}
                    placeholder={`Reply in ${activeChannel.label}`}
                    aria-label={`${activeChannel.label} reply`}
                  />
                  <div>
                    <span>{online ? 'Ready to reply in this channel' : 'Offline: reply will send later'}</span>
                    <button
                      className="primary-action"
                      type="button"
                      onClick={() => sendLiveChatReply(liveConversation, activeDirectChannelId)}
                      disabled={!liveChatDraft.trim()}
                    >
                      <Send size={17} />
                      Reply in {activeChannel.shortLabel}
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-state">
                <strong>No active {activeChannel.label} chats</strong>
                <span>New customer messages will open here.</span>
              </div>
            )}
          </div>
        </div>
      </section>
    )
  }

  function renderChannels() {
    return (
      <div className="screen-stack">
        <section className="channel-flow-grid" aria-label="Channel operating flow">
          {[
            {
              label: 'Intake',
              detail: 'Every channel shows waiting customers, average wait, and health.',
              href: routeHref({ screen: 'channels', channel: 'email' }),
              action: () => setSelectedChannel('email'),
            },
            {
              label: 'Respond',
              detail: 'WhatsApp, Instagram, and Facebook open in their own chat windows.',
              href: routeHref({ screen: 'channels', channel: 'whatsapp' }),
              action: () => openDirectChannel('whatsapp'),
            },
            {
              label: 'Follow through',
              detail: 'Any chat can become a ticket, handoff, note, or resolved update.',
              href: routeHref({ screen: 'handoffs' }),
              action: () => selectScreen('handoffs'),
            },
          ].map(({ label, detail, href, action }) => (
            <a
              className="channel-flow-card"
              href={href}
              key={label}
              onClick={(event) => handleAppLink(event, action)}
            >
              <strong>{label}</strong>
              <span>{detail}</span>
              <em className="card-link-label">
                Open
                <ArrowRight size={14} />
              </em>
            </a>
          ))}
        </section>

        <div className="management-grid live-channel-grid">
          <section className="panel live-channel-table">
            <div className="panel-head">
              <div>
                <span>Channel control</span>
                <h2>Volume, wait time, and availability</h2>
              </div>
              <Headphones size={20} />
            </div>
            <div className="channel-table">
              {state.channels.map((channel) => {
                const Icon = channelIcons[channel.id]
                return (
                  <article
                    className={`channel-row ${state.selectedChannelId === channel.id ? 'active' : ''}`}
                    key={channel.id}
                  >
                    <div className="row-icon">
                      <Icon size={18} />
                    </div>
                    <div>
                      <strong>{channel.label}</strong>
                      <span>{channel.description}</span>
                    </div>
                    <div className="channel-row-meta">
                      <span>{channel.queueDepth} waiting</span>
                      <span>{channel.avgWaitMinutes}m avg wait</span>
                      <span className={`chip status-${channel.status}`}>{titleCase(channel.status)}</span>
                      <button
                        className="secondary-action"
                        type="button"
                        aria-label={
                          isDirectMessageChannel(channel.id)
                            ? `Open ${channel.label} chat workspace`
                            : `Focus ${channel.label} queue`
                        }
                        onClick={() =>
                          isDirectMessageChannel(channel.id)
                            ? openDirectChannel(channel.id)
                            : setSelectedChannel(channel.id)
                        }
                      >
                        {isDirectMessageChannel(channel.id)
                          ? 'Open chat'
                          : 'View queue'}
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          </section>
          {focusedChannel && !isDirectMessageChannel(focusedChannel.id)
            ? renderChannelOverview(focusedChannel)
            : renderDirectChannelChat()}
        </div>
      </div>
    )
  }

  function renderCustomers() {
    return (
      <div className="management-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Customer 360</span>
              <h2>Profiles, value, and open work</h2>
            </div>
            <Users size={20} />
          </div>
          <div className="customer-grid">
            {state.customers.map((customer) => (
              <a
                key={customer.id}
                className={`customer-card ${selectedCustomer.id === customer.id ? 'active' : ''}`}
                href={routeHref({ screen: 'customers', customer: customer.id })}
                onClick={(event) => handleAppLink(event, () => selectCustomer(customer.id))}
                aria-current={selectedCustomer.id === customer.id ? 'true' : undefined}
                aria-label={`Open customer profile for ${customer.name}`}
              >
                <div>
                  <strong>{customer.name}</strong>
                  <span>{customer.company}</span>
                </div>
                <b>{customer.healthScore}</b>
                <small>{customer.recentActivity}</small>
                <div className="tag-list">
                  {customer.tags.slice(0, 2).map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>
              </a>
            ))}
          </div>
        </section>
        {renderCustomer360()}
      </div>
    )
  }

  function renderKnowledge() {
    return (
      <div className="management-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Answers</span>
              <h2>Approved responses and help content</h2>
            </div>
            <BookOpen size={20} />
          </div>
          <div className="data-table">
            {state.articles.map((article) => (
              <article className="data-row" key={article.id}>
                <div>
                  <strong>{article.title}</strong>
                  <span>{article.category} · {article.language}</span>
                </div>
                <span className={`chip status-${article.status}`}>{titleCase(article.status)}</span>
                <span>{article.helpfulness}% useful</span>
                <span>{article.deflection}% resolved without agent</span>
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() => publishArticle(article.id)}
                  disabled={article.status === 'published'}
                  aria-label={`${article.status === 'published' ? 'Published' : 'Publish'} ${article.title}`}
                >
                  {article.status === 'published' ? 'Published' : 'Publish'}
                </button>
              </article>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <span>Best answer now</span>
              <h2>{selectedConversation.copilot.suggestedArticle}</h2>
            </div>
            <Sparkles size={20} />
          </div>
          <p className="panel-copy">{selectedConversation.copilot.summary}</p>
          <div className="tag-list">
            {selectedConversation.copilot.autoTags.map((tag) => (
              <span key={tag}>{tag}</span>
            ))}
          </div>
        </section>
      </div>
    )
  }

  function renderAutomation() {
    return (
      <div className="management-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Routing</span>
              <h2>Rules and response promises</h2>
            </div>
            <Workflow size={20} />
          </div>
          <div className="rule-list">
            {state.rules.map((rule) => (
              <article className="rule-card" key={rule.id}>
                <div>
                  <strong>{rule.name}</strong>
                  <p>{rule.trigger}</p>
                  <span>{rule.condition}</span>
                  <small>{rule.action}</small>
                </div>
                <div>
                  <b>{rule.health}%</b>
                  <span className={`chip status-${rule.status}`}>{titleCase(rule.status)}</span>
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => toggleRule(rule.id)}
                    aria-pressed={rule.status === 'active'}
                  >
                    {rule.status === 'active' ? 'Pause' : 'Activate'}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <span>Promise times</span>
              <h2>Response targets by priority</h2>
            </div>
            <Clock size={20} />
          </div>
          <div className="sla-list">
            {state.slaPolicies.map((policy) => (
              <article key={policy.id}>
                <strong>{policy.name}</strong>
                <span>{titleCase(policy.priority)} · {policy.businessHours}</span>
                <small>{policy.firstResponseMinutes}m first reply · {policy.resolutionMinutes}m full resolution</small>
              </article>
            ))}
          </div>
        </section>
      </div>
    )
  }

  function renderHandoffs() {
    const activeHandoffs = state.handoffs.filter((handoff) => handoff.status !== 'completed')
    const blockedHandoffs = state.handoffs.filter((handoff) => handoff.status === 'blocked')
    const dueSoon = state.handoffs.filter(
      (handoff) =>
        handoff.status !== 'completed' &&
        new Date(handoff.dueAt).getTime() - Date.now() < 90 * 60 * 1000,
    )

    return (
      <div className="screen-stack">
        <section className="handoff-summary-grid" aria-label="Handoff summary">
          {[
            ['Open handoffs', activeHandoffs.length, 'Owned by another team'],
            ['Due soon', dueSoon.length, 'Needs owner confirmation'],
            ['Blocked', blockedHandoffs.length, 'Manager help needed'],
            ['Done', state.handoffs.filter((handoff) => handoff.status === 'completed').length, 'Closed loop'],
          ].map(([label, value, detail]) => (
            <article className="handoff-summary-card" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
              <small>{detail}</small>
            </article>
          ))}
        </section>

        <section className="panel handoff-board-panel">
          <div className="panel-head">
            <div>
              <span>Team ownership</span>
              <h2>Handoff board</h2>
            </div>
            <Handshake size={20} />
          </div>

          <div className="handoff-board">
            {handoffStatusOrder.map((status) => {
              const handoffs = state.handoffs.filter((handoff) => handoff.status === status)
              return (
                <section className="handoff-column" key={status}>
                  <div className="handoff-column-head">
                    <strong>{handoffStatusLabels[status]}</strong>
                    <span>{handoffs.length}</span>
                  </div>

                  {handoffs.map((handoff) => {
                    const customer = state.customers.find((item) => item.id === handoff.customerId)
                    const owner = state.agents.find((agent) => agent.id === handoff.ownerId)
                    const conversation = state.conversations.find(
                      (item) => item.id === handoff.conversationId,
                    )
                    const completedSteps = handoff.checklist.filter((task) => task.done).length
                    const progress = percent(completedSteps, handoff.checklist.length)

                    return (
                      <article className={`handoff-card status-${handoff.status}`} key={handoff.id}>
                        <div className="handoff-card-top">
                          <span className={`chip priority-${handoff.priority}`}>
                            {titleCase(handoff.priority)}
                          </span>
                          <small>Due {formatTime(handoff.dueAt)}</small>
                        </div>
                        <strong>{handoff.ticketNumber}</strong>
                        <p>{handoff.reason}</p>
                        <div className="handoff-route">
                          <span>{handoff.sourceTeam}</span>
                          <ArrowRight size={14} />
                          <span>{handoff.receivingTeam}</span>
                        </div>
                        <small>{customer?.name} · {owner?.name}</small>
                        <div className="handoff-progress">
                          <span>{completedSteps}/{handoff.checklist.length} steps done</span>
                          <b>{progress}%</b>
                        </div>
                        <div className="health-track">
                          <span style={{ width: `${progress}%` }} />
                        </div>
                        <div className="handoff-checklist">
                          {handoff.checklist.map((task) => (
                            <label key={task.id}>
                              <input
                                type="checkbox"
                                checked={task.done}
                                onChange={() => toggleHandoffChecklist(handoff.id, task.id)}
                              />
                              {task.label}
                            </label>
                          ))}
                        </div>
                        {handoff.blockers.length > 0 && (
                          <div className="handoff-blockers">
                            {handoff.blockers.map((blocker) => (
                              <span key={blocker}>{blocker}</span>
                            ))}
                          </div>
                        )}
                        <div className="handoff-actions">
                          <select
                            value={handoff.status}
                            onChange={(event) =>
                              updateHandoffStatus(handoff.id, event.target.value as HandoffStatus)
                            }
                            aria-label={`${handoff.id} status`}
                          >
                            {handoffStatusOrder.map((option) => (
                              <option value={option} key={option}>
                                {handoffStatusLabels[option]}
                              </option>
                            ))}
                          </select>
                          {conversation && (
                            <a
                              className="secondary-action"
                              href={routeHref({
                                screen: 'inbox',
                                conversation: conversation.id,
                                customer: conversation.customerId,
                              })}
                              onClick={(event) => handleAppLink(event, () => openConversationInInbox(conversation))}
                              aria-label={`Open ${conversation.ticketNumber} ticket`}
                            >
                              View ticket
                            </a>
                          )}
                        </div>
                      </article>
                    )
                  })}
                </section>
              )
            })}
          </div>
        </section>
      </div>
    )
  }

  function renderAnalytics() {
    const maxQueue = Math.max(...state.channels.map((channel) => channel.queueDepth), 1)
    return (
      <div className="management-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Reporting</span>
              <h2>Channel volume and on-time performance</h2>
            </div>
            <BarChart3 size={20} />
          </div>
          <div className="bar-list">
            {state.channels.map((channel) => (
              <div className="bar-row" key={channel.id}>
                <span>{channel.label}</span>
                <div className="bar-track">
                  <span style={{ width: `${percent(channel.queueDepth, maxQueue)}%` }} />
                </div>
                <strong>{channel.queueDepth}</strong>
              </div>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <span>Quality</span>
              <h2>Service signals</h2>
            </div>
            <Gauge size={20} />
          </div>
          <div className="signal-grid">
            <div><strong>{metrics.csat}</strong><span>Average CSAT</span></div>
            <div><strong>{metrics.avgHealth}%</strong><span>Channel health</span></div>
            <div><strong>{metrics.atRisk}</strong><span>At-risk work</span></div>
            <div><strong>{metrics.avgOccupancy}%</strong><span>Occupancy</span></div>
          </div>
        </section>
      </div>
    )
  }

  function renderWorkforce() {
    return (
      <div className="management-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Staffing</span>
              <h2>Agent capacity and coverage</h2>
            </div>
            <UserCheck size={20} />
          </div>
          <div className="workforce-list">
            {state.agents.map((agent) => (
              <article className="workforce-row" key={agent.id}>
                <div className="avatar">{agent.avatar}</div>
                <div>
                  <strong>{agent.name}</strong>
                  <span>{agent.role} · {agent.shift}</span>
                </div>
                <span>{agent.load}/{agent.capacity} active</span>
                <span>{agent.occupancy}% occupied</span>
                <span className={`availability ${agent.availability}`}>{titleCase(agent.availability)}</span>
              </article>
            ))}
          </div>
        </section>
      </div>
    )
  }

  function renderAdmin() {
    const connectorAccounts = backendSnapshot?.connectorAccounts ?? []
    const outboundMessages = backendSnapshot?.outboundMessages ?? []
    const failedOutboundMessages = outboundMessages.filter((message) =>
      ['failed', 'retrying', 'dead_lettered'].includes(message.status),
    )
    const platformUsers = backendSnapshot?.users ?? []
    const marketNameById = new Map(availableMarkets.map((market) => [market.id, `${market.code} · ${market.name}`]))
    const canManageUsers = backendSession?.user.role === 'admin'
    return (
      <div className="management-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Setup</span>
              <h2>Controls and readiness</h2>
            </div>
            <ShieldCheck size={20} />
          </div>
          <div className="admin-grid">
            {[
              ['People and roles', 'Agent, supervisor, admin, and auditor access with team boundaries.'],
              ['Ticket fields', 'Status, priority, source, customer mood, topic, and custom fields.'],
              ['Channel connections', 'Email, chat, phone, WhatsApp, SMS, social, portal, and partner systems.'],
              ['Security controls', 'Audit trail, permissions, tenant separation, attachments, and data retention.'],
              ['Working status', `${online ? 'Online' : 'Offline'} · ${state.outbox.length} pending send(s).`],
              [
                'Backend sync',
                backendSync.status === 'connected'
                  ? `Connected to ${backendSync.baseUrl}.`
                  : backendSync.status === 'syncing'
                    ? `Syncing ${backendSync.baseUrl}.`
                    : backendSync.error || `Waiting to reach ${backendSync.baseUrl}.`,
              ],
              ['Review refresh', 'Restore the approved walkthrough data.'],
            ].map(([title, body]) => (
              <article key={title}>
                <Lock size={18} />
                <strong>{title}</strong>
                <span>{body}</span>
              </article>
            ))}
          </div>
          <div className="automation-settings-panel user-management-panel">
            <div className="panel-head compact">
              <div>
                <span>People management</span>
                <h2>Users, roles, and markets</h2>
              </div>
              <Users size={18} />
            </div>
            <form className="user-create-form" onSubmit={handleCreateUser}>
              <label>
                <span>Name</span>
                <input
                  required
                  value={newUser.name}
                  onChange={(event) => setNewUser((current) => ({ ...current, name: event.target.value }))}
                  placeholder="Agent name"
                  disabled={!canManageUsers}
                />
              </label>
              <label>
                <span>Email</span>
                <input
                  required
                  type="email"
                  value={newUser.email}
                  onChange={(event) => setNewUser((current) => ({ ...current, email: event.target.value }))}
                  placeholder="agent@company.com"
                  disabled={!canManageUsers}
                />
              </label>
              <label>
                <span>Role</span>
                <select
                  value={newUser.role}
                  onChange={(event) =>
                    setNewUser((current) => ({
                      ...current,
                      role: event.target.value as (typeof userRoleOptions)[number],
                    }))
                  }
                  disabled={!canManageUsers}
                >
                  {userRoleOptions.map((role) => (
                    <option key={role} value={role}>
                      {titleCase(role)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Default market</span>
                <select
                  value={newUser.defaultMarketId}
                  onChange={(event) =>
                    setNewUser((current) => ({
                      ...current,
                      defaultMarketId: event.target.value,
                      marketIds: current.marketIds.includes(event.target.value)
                        ? current.marketIds
                        : [...current.marketIds, event.target.value],
                    }))
                  }
                  disabled={!canManageUsers}
                >
                  {availableMarkets.map((market) => (
                    <option key={market.id} value={market.id}>
                      {market.code} · {market.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="user-market-picker" aria-label="Assigned markets">
                <span>Assigned markets</span>
                <div>
                  {availableMarkets.map((market) => (
                    <label key={market.id}>
                      <input
                        type="checkbox"
                        checked={newUser.marketIds.includes(market.id)}
                        onChange={() => toggleNewUserMarket(market.id)}
                        disabled={!canManageUsers}
                      />
                      {market.code}
                    </label>
                  ))}
                </div>
              </div>
              <button className="primary-action" type="submit" disabled={!canManageUsers}>
                <Plus size={16} />
                Add user
              </button>
            </form>
            <div className="user-list" aria-label="Backend users">
              {platformUsers.map((user) => (
                <article className={`user-card ${user.active ? 'active' : 'inactive'}`} key={user.id}>
                  <div className="user-card-head">
                    <div className="avatar">{initials(user.name)}</div>
                    <div>
                      <strong>{user.name}</strong>
                      <span>{user.email}</span>
                    </div>
                    <em className={`chip status-${user.active ? 'healthy' : 'paused'}`}>
                      {user.active ? 'Active' : 'Inactive'}
                    </em>
                  </div>
                  <div className="user-card-controls">
                    <label>
                      <span>Role</span>
                      <select
                        value={user.role}
                        onChange={(event) =>
                          updateUser(user.id, {
                            role: event.target.value as (typeof userRoleOptions)[number],
                          })
                        }
                        disabled={!canManageUsers}
                      >
                        {userRoleOptions.map((role) => (
                          <option key={role} value={role}>
                            {titleCase(role)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Default market</span>
                      <select
                        value={user.default_market_id}
                        onChange={(event) => {
                          const defaultMarketId = event.target.value
                          updateUser(user.id, {
                            default_market_id: defaultMarketId,
                            market_ids: user.market_ids.includes(defaultMarketId)
                              ? user.market_ids
                              : [...user.market_ids, defaultMarketId],
                          })
                        }}
                        disabled={!canManageUsers}
                      >
                        {availableMarkets.map((market) => (
                          <option key={market.id} value={market.id}>
                            {market.code}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => updateUser(user.id, { active: !user.active })}
                      disabled={!canManageUsers || user.id === backendSession?.user.id}
                    >
                      {user.active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  </div>
                  <div className="user-market-list" aria-label={`${user.name} market access`}>
                    {availableMarkets.map((market) => {
                      const checked = user.market_ids.includes(market.id)
                      return (
                        <label key={market.id}>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => {
                              const nextMarketIds = checked
                                ? user.market_ids.filter((item) => item !== market.id)
                                : [...user.market_ids, market.id]
                              if (nextMarketIds.length === 0) return
                              updateUser(user.id, {
                                market_ids: nextMarketIds,
                                default_market_id: nextMarketIds.includes(user.default_market_id)
                                  ? user.default_market_id
                                  : nextMarketIds[0],
                              })
                            }}
                            disabled={!canManageUsers}
                          />
                          {marketNameById.get(market.id) ?? market.id}
                        </label>
                      )
                    })}
                  </div>
                </article>
              ))}
              {platformUsers.length === 0 ? (
                <article className="user-card empty">
                  <strong>No backend users loaded</strong>
                  <span>Refresh backend sync after the API starts.</span>
                </article>
              ) : null}
            </div>
          </div>
          <div className="automation-settings-panel">
            <div className="panel-head compact">
              <div>
                <span>Backend bridge</span>
                <h2>Independent API status</h2>
              </div>
              <RefreshCw size={18} />
            </div>
            <div className="automation-scope" aria-label="Backend integration status">
              <article>
                <CheckCircle2 size={16} />
                <strong>API health</strong>
                <span>{backendSnapshot?.health.status ?? 'Unavailable'}</span>
              </article>
              <article>
                <CheckCircle2 size={16} />
                <strong>Tracker status</strong>
                <span>{backendSnapshot?.tracker.current_status ?? 'Backend tracker not loaded yet.'}</span>
              </article>
              <article>
                <CheckCircle2 size={16} />
                <strong>Queue snapshot</strong>
                <span>
                  {backendSnapshot
                    ? `${backendSnapshot.analytics.open_tickets} open, ${backendSnapshot.analytics.at_risk_tickets} at risk, ${backendSnapshot.analytics.breached_tickets} breached.`
                    : 'No backend analytics snapshot yet.'}
                </span>
              </article>
              <article>
                <CheckCircle2 size={16} />
                <strong>Connector readiness</strong>
                <span>
                  {backendSnapshot
                    ? `${connectorAccounts.length} market connector account(s) loaded from the backend.`
                    : 'Connector provider metadata unavailable.'}
                </span>
              </article>
            </div>
            <button className="secondary-action" type="button" onClick={() => refreshBackend()}>
              <RefreshCw size={16} />
              Refresh backend sync
            </button>
            {backendSync.lastSyncAt ? <small>Last sync: {formatTime(backendSync.lastSyncAt)}</small> : null}
          </div>
          <div className="automation-settings-panel connector-control-center">
            <div className="panel-head compact">
              <div>
                <span>Connector control center</span>
                <h2>Market channel accounts</h2>
              </div>
              <Wifi size={18} />
            </div>
            <div className="connector-account-grid" aria-label="Market connector accounts">
              {connectorAccounts.map((account) => {
                const providerId = (account.provider === 'voice' ? 'phone' : account.provider) as ChannelId
                const Icon = channelIcons[providerId] ?? MessageCircle
                const tone = connectorStatusTone(account.status)
                return (
                  <article className="connector-account-card" key={account.id}>
                    <div className="connector-account-head">
                      <span className="channel-icon">
                        <Icon size={18} />
                      </span>
                      <div>
                        <strong>{account.display_name}</strong>
                        <small>{account.account_identifier || 'Account pending'}</small>
                      </div>
                      <span className={`chip status-${tone}`}>{titleCase(connectorStatusLabel(account.status))}</span>
                    </div>
                    <div className="connector-readiness-grid">
                      <span>
                        <b>Credentials</b>
                        {account.secret_configured ? 'Stored reference' : 'Required'}
                      </span>
                      <span>
                        <b>Webhook</b>
                        {account.webhook_verified ? 'Verified' : 'Not verified'}
                      </span>
                      <span>
                        <b>Replies</b>
                        {account.outbound_enabled ? 'Allowed' : 'Blocked'}
                      </span>
                      <span>
                        <b>Failures</b>
                        {account.failure_count}
                      </span>
                    </div>
                    <div className="connector-webhook-row">
                      <span>Webhook</span>
                      <code>{account.webhook_url}</code>
                    </div>
                    <div className="connector-chip-row" aria-label={`${account.display_name} capabilities`}>
                      {account.capabilities.slice(0, 4).map((capability) => (
                        <span className="mini-chip" key={capability}>
                          {capability}
                        </span>
                      ))}
                    </div>
                    {!account.secret_configured ? (
                      <div className="connector-needed">
                        <AlertTriangle size={15} />
                        <span>{account.required_credentials.slice(0, 2).join(' · ')}</span>
                      </div>
                    ) : null}
                    {account.last_error ? (
                      <div className="connector-needed error">
                        <AlertTriangle size={15} />
                        <span>{account.last_error}</span>
                      </div>
                    ) : null}
                  </article>
                )
              })}
            </div>
          </div>
          <div className="automation-settings-panel outbound-queue-panel" id="outbound-queue">
            <div className="panel-head compact">
              <div>
                <span>Outbound queue</span>
                <h2>Customer send pipeline</h2>
              </div>
              <Send size={18} />
            </div>
            <div className="outbound-summary-grid" aria-label="Outbound delivery summary">
              {[
                ['Queued', outboundMessages.filter((message) => message.status === 'queued').length],
                ['Sending', outboundMessages.filter((message) => message.status === 'sending' || message.status === 'retrying').length],
                ['Sent', outboundMessages.filter((message) => message.status === 'sent').length],
                ['Failed', failedOutboundMessages.length],
              ].map(([label, value]) => (
                <article key={label}>
                  <strong>{value}</strong>
                  <span>{label}</span>
                </article>
              ))}
            </div>
            <div className="outbound-message-list" aria-label="Outbound messages needing attention">
              {failedOutboundMessages.slice(0, 5).map((message) => (
                <article key={message.id}>
                  <div>
                    <strong>{titleCase(message.provider)} reply</strong>
                    <span>{message.last_error ?? 'Waiting for connector retry.'}</span>
                    <small>{message.attempts}/{message.max_attempts} attempt(s)</small>
                  </div>
                  <em className={`chip status-${message.status === 'dead_lettered' ? 'failing' : 'pending'}`}>
                    {deliveryLabel(message.status)}
                  </em>
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => {
                      retryOutboundMessage(message.id)
                      setPrototypeNotice('Outbound retry requested.')
                    }}
                  >
                    <RefreshCw size={15} />
                    Retry
                  </button>
                </article>
              ))}
              {failedOutboundMessages.length === 0 ? (
                <article className="outbound-empty">
                  <CheckCircle2 size={16} />
                  <span>No failed sends need attention.</span>
                </article>
              ) : null}
            </div>
          </div>
          <div className="automation-settings-panel">
            <div className="panel-head compact">
              <div>
                <span>AI queue control</span>
                <h2>Work Queue automation</h2>
              </div>
              <Bot size={18} />
            </div>
            <label className="setting-row">
              <span>
                <strong>Automate triage, routing, priority, and owner assignment</strong>
                <small>
                  Default for backend development: AI keeps the Work Queue moving unless this switch is turned off by an admin.
                </small>
              </span>
              <input
                type="checkbox"
                role="switch"
                checked={aiWorkQueueAutomationEnabled}
                onChange={(event) =>
                  updateSettings({ aiWorkQueueAutomationEnabled: event.target.checked })
                }
              />
            </label>
            <div className="automation-scope" aria-label="AI automation scope">
              {[
                ['Intake', 'Classify source, topic, priority, sentiment, and SLA risk.'],
                ['Routing', 'Choose queue, group, and best available owner by skill and load.'],
                ['Next action', 'Suggest response, article, escalation, and handoff path.'],
                ['Guardrail', 'Admin can disable automation; agents still review before customer send.'],
              ].map(([title, body]) => (
                <article key={title}>
                  <CheckCircle2 size={16} />
                  <strong>{title}</strong>
                  <span>{body}</span>
                </article>
              ))}
            </div>
          </div>
          <button className="secondary-action" type="button" onClick={resetDemo}>
            <RotateCcw size={16} />
            Reset review data
          </button>
        </section>
      </div>
    )
  }

  function renderTracker() {
    return (
      <div className="management-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Delivery</span>
              <h2>Build plan and approval status</h2>
            </div>
            <GitBranch size={20} />
          </div>
          <div className="epic-grid">
            {state.epics.map((epic) => (
              <article className="epic-card" key={epic.id}>
                <span className={`chip status-${epic.status}`}>{titleCase(epic.status)}</span>
                <strong>{epic.id} · {epic.title}</strong>
                <p>{epic.outcome}</p>
                <div className="health-track">
                  <span style={{ width: `${epic.progress}%` }} />
                </div>
                <small>{epic.pending}</small>
              </article>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <span>Backend milestone</span>
              <h2>Independent API progress</h2>
            </div>
            <Activity size={20} />
          </div>
          <div className="compact-list">
            <div>
              <strong>Status</strong>
              <span>{backendSnapshot?.tracker.current_status ?? 'Backend tracker pending sync.'}</span>
              <em className={`chip status-${backendSync.status === 'connected' ? 'done' : 'pending'}`}>
                {titleCase(backendSync.status)}
              </em>
            </div>
            {(backendSnapshot?.tracker.epics ?? []).map((epic) => (
              <div key={epic}>
                <strong>Epic</strong>
                <span>{epic}</span>
                <em className="chip status-in-progress">Backend</em>
              </div>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <span>Backlog</span>
              <h2>Current status</h2>
            </div>
            <ClipboardList size={20} />
          </div>
          <div className="compact-list">
            {state.backlog.map((item) => (
              <div key={item.id}>
                <strong>{item.id}</strong>
                <span>{item.title}</span>
                <em className={`chip status-${item.status}`}>{titleCase(item.status)}</em>
              </div>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <span>Dependencies</span>
              <h2>Backend production blockers</h2>
            </div>
            <AlertTriangle size={20} />
          </div>
          <div className="compact-list">
            {(backendSnapshot?.tracker.known_dependencies ?? []).map((dependency) => (
              <div key={dependency}>
                <strong>Need</strong>
                <span>{dependency}</span>
                <em className="chip status-pending">Pending</em>
              </div>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <span>Issues</span>
              <h2>Closed and pending</h2>
            </div>
            <CheckCircle2 size={20} />
          </div>
          <div className="compact-list">
            {state.issues.map((issue) => (
              <div key={issue.id}>
                <strong>{issue.id}</strong>
                <span>{issue.title}</span>
                <em className={`chip status-${issue.status}`}>{titleCase(issue.status)}</em>
              </div>
            ))}
          </div>
        </section>
      </div>
    )
  }

  function renderScreen() {
    if (state.selectedScreen === 'command') return renderCommand()
    if (state.selectedScreen === 'inbox') return renderInbox()
    if (state.selectedScreen === 'channels') return renderChannels()
    if (state.selectedScreen === 'customers') return renderCustomers()
    if (state.selectedScreen === 'knowledge') return renderKnowledge()
    if (state.selectedScreen === 'automation') return renderAutomation()
    if (state.selectedScreen === 'handoffs') return renderHandoffs()
    if (state.selectedScreen === 'analytics') return renderAnalytics()
    if (state.selectedScreen === 'workforce') return renderWorkforce()
    if (state.selectedScreen === 'admin') return renderAdmin()
    return renderTracker()
  }

  const currentScreen = screenConfig.find((item) => item.id === state.selectedScreen) ?? screenConfig[0]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand-lockup"
          href={routeHref({ screen: 'command' })}
          onClick={(event) => handleAppLink(event, () => selectScreen('command'))}
          aria-label="Go to Omni Command home"
        >
          <div className="brand-mark">
            <LifeBuoy size={23} />
          </div>
          <div>
            <strong>Omni Ticket</strong>
            <span>Operations support</span>
          </div>
        </a>
        <nav className="side-nav" aria-label="Primary navigation">
          {screenConfig.map((item) => renderNavItem(item))}
        </nav>
        <div className="sidebar-footer">
          <div className={`connectivity ${online ? 'online' : 'offline'}`}>
            {online ? <Wifi size={15} /> : <WifiOff size={15} />}
            <span>{online ? 'Online' : 'Offline sends queued'}</span>
          </div>
          <label className="market-switcher">
            <span>Market</span>
            <select
              value={currentMarket?.id ?? ''}
              onChange={(event) => switchMarket(event.target.value)}
            >
              {availableMarkets.map((market) => (
                <option value={market.id} key={market.id}>
                  {market.code} · {market.name}
                </option>
              ))}
            </select>
          </label>
          <div className="mini-profile">
            <div className="avatar">
              {backendSession.user.name
                .split(' ')
                .map((part) => part[0])
                .join('')
                .slice(0, 2)}
            </div>
            <div>
              <strong>{backendSession.user.name}</strong>
              <span>{titleCase(backendSession.user.role)} · {currentMarket?.code}</span>
            </div>
          </div>
          <button className="text-action" type="button" onClick={() => logout()}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <div>
            <span className="section-kicker">Omni Ticket operations support</span>
            <h1>{currentScreen.label}</h1>
            <p className="screen-lead">
              {currentMarket ? `${currentMarket.name} market · ` : ''}
              {screenLead[currentScreen.id]}
            </p>
          </div>
          <div className="topbar-actions">
            <div className="global-search">
              <Search size={16} />
              <input
                value={state.filters.search}
                onChange={(event) => setFilters({ search: event.target.value })}
                placeholder="Search customers, conversations, tags"
                aria-label="Global search"
              />
            </div>
            <button
              className="icon-button"
              type="button"
              aria-label="Notifications"
              aria-expanded={notificationOpen}
              onClick={() => setNotificationOpen((value) => !value)}
            >
              <Bell size={18} />
            </button>
            <a
              className="primary-action"
              href={routeHref({ screen: 'inbox' })}
              onClick={(event) => handleAppLink(event, () => selectScreen('inbox'))}
            >
              <MessageSquare size={17} />
              Work inbox
            </a>
          </div>
        </header>

        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {prototypeNotice}
        </div>
        {prototypeNotice && <div className="prototype-toast">{prototypeNotice}</div>}
        {renderNotificationPanel()}

        {!online && (
          <div className="offline-banner">
            <WifiOff size={17} />
            Offline mode. Replies and handoffs will wait here and send when the connection returns.
          </div>
        )}

        {renderScreen()}
      </main>

      <nav className="mobile-nav" aria-label="Mobile navigation">
        {screenConfig.map((item) => renderNavItem(item))}
      </nav>
      {renderQuickCreatePanel()}
    </div>
  )
}

export default OmniApp
