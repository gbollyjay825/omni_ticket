import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Bell,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  CircleUserRound,
  Clock3,
  Inbox,
  Keyboard,
  LayoutDashboard,
  Link2,
  LoaderCircle,
  MessageCircle,
  MoreHorizontal,
  Paperclip,
  PanelRight,
  Plus,
  Search,
  Send,
  Settings,
  Smile,
  Sparkles,
  TicketCheck,
  UserRoundCheck,
  Users,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { BackendSession } from '../../backend'
import { useOmnichatRealtime } from './useOmnichatRealtime'
import {
  assignConversation,
  changeConversationStatus,
  conversationAttachmentDownloadUrl,
  createConversation,
  createConversationMessage,
  fetchConversation,
  fetchConversationContext,
  fetchConversationMessages,
  fetchConversations,
  fetchConversationTopics,
  fetchConversationViews,
  fetchCustomers,
  fetchCustomerTickets,
  fetchFeatureCapabilities,
  fetchResponseMacros,
  fetchSupportGroups,
  fetchUsers,
  linkConversationTicket,
  intelliAssignConversation,
  markConversationMessageRead,
  updateConversation,
  uploadConversationAttachment,
  type Conversation,
  type ConversationAttachment,
} from './api'
import './omnichat-workspace.css'

interface OmnichatWorkspaceProps {
  session: BackendSession
  online: boolean
  onNavigate: (screen: string) => void
  onSwitchMarket: (marketId: string) => void
  onSignOut: () => void
}

type ComposerMode = 'reply' | 'private'
type MobilePane = 'queue' | 'thread' | 'context'
const CONVERSATION_REALTIME_AGGREGATES = new Set([
  'conversation',
  'conversation_assignment',
  'conversation_message',
  'conversation_ticket_link',
  'message_receipt',
])

function initials(name: string) {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function formatActivityTime(value: string) {
  const date = new Date(value)
  const elapsed = Date.now() - date.getTime()
  if (elapsed < 60_000) return 'now'
  if (elapsed < 3_600_000) return `${Math.floor(elapsed / 60_000)}m`
  if (elapsed < 86_400_000) return `${Math.floor(elapsed / 3_600_000)}h`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function readableChannel(channel: string) {
  return channel.charAt(0).toUpperCase() + channel.slice(1)
}

function deliveryLabel(state: string) {
  if (state === 'pending_provider') return 'Provider not configured'
  if (state === 'queued' || state === 'sending' || state === 'retrying') return 'Sending'
  if (state === 'failed') return 'Delivery failed'
  if (state === 'dead_lettered') return 'Delivery stopped'
  if (state === 'sent') return 'Sent'
  if (state === 'delivered') return 'Delivered'
  if (state === 'read') return 'Read'
  if (state === 'internal') return 'Private note'
  if (state === 'received') return 'Received'
  return state.replaceAll('_', ' ')
}

export function OmnichatWorkspace({
  session,
  online,
  onNavigate,
  onSwitchMarket,
  onSignOut,
}: OmnichatWorkspaceProps) {
  const queryClient = useQueryClient()
  const initialConversationId = new URLSearchParams(window.location.search).get('conversation') ?? ''
  const [selectedConversationId, setSelectedConversationId] = useState(initialConversationId)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('open,pending')
  const [selectedViewId, setSelectedViewId] = useState('')
  const [composerMode, setComposerMode] = useState<ComposerMode>('reply')
  const [draft, setDraft] = useState('')
  const [pendingAttachments, setPendingAttachments] = useState<ConversationAttachment[]>([])
  const [notice, setNotice] = useState('')
  const [newConversationOpen, setNewConversationOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [newConversation, setNewConversation] = useState({
    customerId: '',
    channel: 'whatsapp',
    subject: '',
    message: '',
  })
  const [mobilePane, setMobilePane] = useState<MobilePane>('queue')
  const [contextExpanded, setContextExpanded] = useState({ details: true, history: true, tickets: true, attachments: true })
  const typingTimer = useRef<number | undefined>(undefined)
  const savedViewSelect = useRef<HTMLSelectElement>(null)
  const composerInput = useRef<HTMLTextAreaElement>(null)
  const attachmentInput = useRef<HTMLInputElement>(null)

  const featureQuery = useQuery({
    queryKey: ['features', session.market.id],
    queryFn: () => fetchFeatureCapabilities(session),
  })
  const viewsQuery = useQuery({
    queryKey: ['conversation-views', session.market.id, session.user.id],
    queryFn: () => fetchConversationViews(session),
  })
  const topicsQuery = useQuery({
    queryKey: ['conversation-topics', session.market.id],
    queryFn: () => fetchConversationTopics(session),
  })
  const usersQuery = useQuery({
    queryKey: ['omnichat-users', session.market.id],
    queryFn: () => fetchUsers(session),
  })
  const groupsQuery = useQuery({
    queryKey: ['omnichat-groups', session.market.id],
    queryFn: () => fetchSupportGroups(session),
  })
  const macrosQuery = useQuery({
    queryKey: ['omnichat-macros', session.market.id],
    queryFn: () => fetchResponseMacros(session),
  })
  const customersQuery = useQuery({
    queryKey: ['omnichat-customers', session.market.id],
    queryFn: () => fetchCustomers(session),
    enabled: newConversationOpen,
  })
  const conversationsQuery = useQuery({
    queryKey: [
      'conversations',
      session.market.id,
      session.user.id,
      search,
      statusFilter,
      selectedViewId,
    ],
    queryFn: () =>
      fetchConversations(session, {
        limit: 50,
        status: statusFilter || undefined,
        viewId: selectedViewId || undefined,
        query: search.trim().length > 1 ? search.trim() : undefined,
      }),
  })
  const conversations = useMemo(
    () => conversationsQuery.data?.items ?? [],
    [conversationsQuery.data?.items],
  )
  const activeConversationId = selectedConversationId || conversations[0]?.id || ''
  const conversationQuery = useQuery({
    queryKey: ['conversation', session.market.id, activeConversationId],
    queryFn: () => fetchConversation(session, activeConversationId),
    enabled: Boolean(activeConversationId),
  })
  const messagesQuery = useQuery({
    queryKey: ['conversation-messages', session.market.id, activeConversationId],
    queryFn: () => fetchConversationMessages(session, activeConversationId),
    enabled: Boolean(activeConversationId),
  })
  const contextQuery = useQuery({
    queryKey: ['conversation-context', session.market.id, activeConversationId],
    queryFn: () => fetchConversationContext(session, activeConversationId),
    enabled: Boolean(activeConversationId),
  })
  const customerTicketsQuery = useQuery({
    queryKey: [
      'conversation-customer-tickets',
      session.market.id,
      contextQuery.data?.customer.id,
    ],
    queryFn: () => fetchCustomerTickets(session, contextQuery.data!.customer.id),
    enabled: Boolean(contextQuery.data?.customer.id),
  })

  const refreshConversation = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['conversations', session.market.id] }),
      queryClient.invalidateQueries({
        queryKey: ['conversation', session.market.id, activeConversationId],
      }),
      queryClient.invalidateQueries({
        queryKey: ['conversation-messages', session.market.id, activeConversationId],
      }),
      queryClient.invalidateQueries({
        queryKey: ['conversation-context', session.market.id, activeConversationId],
      }),
    ])
  }

  const { connectionStatus, typingByConversation, sendTyping, markRead } = useOmnichatRealtime({
    session,
    online,
    onDurableEvent: (event) => {
      if (!CONVERSATION_REALTIME_AGGREGATES.has(event.aggregate_type)) return
      if (event.aggregate_id === activeConversationId || event.payload.conversation_id === activeConversationId) {
        void refreshConversation()
      } else {
        void queryClient.invalidateQueries({ queryKey: ['conversations', session.market.id] })
      }
    },
  })

  const conversation = conversationQuery.data
  const context = contextQuery.data
  const messages = useMemo(() => messagesQuery.data?.items ?? [], [messagesQuery.data?.items])
  const typingActors = typingByConversation[activeConversationId] ?? []

  useEffect(() => {
    const latestCustomerMessage = [...messages]
      .reverse()
      .find((message) => message.sender_type === 'customer' && message.visibility === 'public')
    if (!latestCustomerMessage || !activeConversationId) return
    markRead(activeConversationId, latestCustomerMessage.id)
    void markConversationMessageRead(session, activeConversationId, latestCustomerMessage.id).then(
      () => queryClient.invalidateQueries({ queryKey: ['conversations', session.market.id] }),
    )
  }, [activeConversationId, markRead, messages, queryClient, session])

  const sendMutation = useMutation({
    mutationFn: async () => {
      if (!conversation || (!draft.trim() && pendingAttachments.length === 0)) return null
      return createConversationMessage(session, conversation.id, {
        expected_version: conversation.version,
        body: draft.trim(),
        visibility: composerMode === 'private' ? 'private' : 'public',
        content: { attachment_ids: pendingAttachments.map((attachment) => attachment.id) },
        idempotency_key: crypto.randomUUID(),
      })
    },
    onSuccess: (message) => {
      if (!message) return
      setDraft('')
      setPendingAttachments([])
      sendTyping(activeConversationId, false)
      setNotice(
        message.delivery_state === 'failed' || message.delivery_state === 'dead_lettered'
          ? String(message.metadata.delivery_error || 'Reply saved, but provider delivery failed.')
          : ['queued', 'sending', 'retrying', 'pending_provider'].includes(message.delivery_state)
            ? 'Reply saved and queued for provider delivery.'
          : composerMode === 'private'
            ? 'Private note added.'
            : 'Reply sent.',
      )
      void refreshConversation()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Reply failed.'),
  })

  const attachmentMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!conversation) throw new Error('Select a conversation before adding an attachment.')
      return uploadConversationAttachment(session, conversation.id, file)
    },
    onSuccess: (attachment) => {
      if (attachment.scan_status === 'clean') {
        setPendingAttachments((current) => [...current, attachment])
      }
      setNotice(
        attachment.scan_status === 'clean'
          ? `${attachment.filename} is ready to send.`
          : `${attachment.filename} was blocked by the attachment policy.`,
      )
      void refreshConversation()
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : 'Attachment upload failed.')
    },
  })

  const statusMutation = useMutation({
    mutationFn: (action: 'resolve' | 'reopen') => {
      if (!conversation) throw new Error('Select a conversation first.')
      return changeConversationStatus(session, conversation.id, action, {
        expected_version: conversation.version,
        reason: action === 'resolve' ? 'Resolved from Omnichat workspace' : 'Reopened by agent',
      })
    },
    onSuccess: () => void refreshConversation(),
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Status update failed.'),
  })

  const sendAndResolveMutation = useMutation({
    mutationFn: async () => {
      if (!conversation || (!draft.trim() && pendingAttachments.length === 0)) {
        throw new Error('Enter a reply or attach a file first.')
      }
      await createConversationMessage(session, conversation.id, {
        expected_version: conversation.version,
        body: draft.trim(),
        visibility: composerMode === 'private' ? 'private' : 'public',
        content: { attachment_ids: pendingAttachments.map((attachment) => attachment.id) },
        idempotency_key: crypto.randomUUID(),
      })
      const current = await fetchConversation(session, conversation.id)
      if (current.status !== 'resolved' && current.status !== 'closed') {
        await changeConversationStatus(session, current.id, 'resolve', {
          expected_version: current.version,
          reason: 'Sent and resolved from Omnichat workspace',
        })
      }
    },
    onSuccess: () => {
      setDraft('')
      setPendingAttachments([])
      sendTyping(activeConversationId, false)
      setNotice('Reply sent and conversation resolved.')
      void refreshConversation()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Send and resolve failed.'),
  })

  const assignmentMutation = useMutation({
    mutationFn: (change: { assigneeId?: string; groupId?: string }) => {
      if (!conversation) throw new Error('Select a conversation first.')
      return assignConversation(session, conversation.id, {
        expected_version: conversation.version,
        assignee_id:
          change.assigneeId === undefined ? conversation.assignee_id : change.assigneeId || null,
        group_id:
          change.groupId === undefined ? conversation.assigned_group_id : change.groupId || null,
        reason: 'Updated from Omnichat workspace',
      })
    },
    onSuccess: () => void refreshConversation(),
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Assignment failed.'),
  })

  const intelliAssignMutation = useMutation({
    mutationFn: () => {
      if (!conversation) throw new Error('Select a conversation first.')
      return intelliAssignConversation(session, conversation.id, {
        expected_version: conversation.version,
        reason: 'IntelliAssign from Omnichat workspace',
      })
    },
    onSuccess: (assigned) => {
      setNotice(`Assigned to ${assigned.assignee_name || 'the least-loaded operator'}.`)
      void refreshConversation()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'IntelliAssign failed.'),
  })

  const topicMutation = useMutation({
    mutationFn: (topicId: string) => {
      if (!conversation) throw new Error('Select a conversation first.')
      return updateConversation(session, conversation.id, {
        expected_version: conversation.version,
        topic_id: topicId || null,
      })
    },
    onSuccess: () => void refreshConversation(),
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Topic update failed.'),
  })

  const linkMutation = useMutation({
    mutationFn: (ticketId: string) => linkConversationTicket(session, activeConversationId, ticketId),
    onSuccess: () => {
      setNotice('Ticket linked to this conversation.')
      void queryClient.invalidateQueries({
        queryKey: ['conversation-context', session.market.id, activeConversationId],
      })
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Ticket link failed.'),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      createConversation(session, {
        customer_id: newConversation.customerId,
        channel: newConversation.channel as Conversation['channel'],
        subject: newConversation.subject,
        priority: 'normal',
        initial_message: newConversation.message,
        initial_sender: 'customer',
        metadata: { source: 'agent_workspace' },
      }),
    onSuccess: (created) => {
      setNewConversationOpen(false)
      setPendingAttachments([])
      setSelectedConversationId(created.id)
      setMobilePane('thread')
      setNewConversation({ customerId: '', channel: 'whatsapp', subject: '', message: '' })
      void queryClient.invalidateQueries({ queryKey: ['conversations', session.market.id] })
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Conversation failed.'),
  })

  const selectedView = viewsQuery.data?.find((view) => view.id === selectedViewId)
  const canUseWorkspace =
    session.user.role === 'admin' ||
    featureQuery.data?.some((feature) => feature.key === 'omnichat_parity' && feature.available)

  const candidateTickets = useMemo(() => {
    const linked = new Set(context?.linked_tickets.map((ticket) => ticket.id) ?? [])
    return (customerTicketsQuery.data ?? []).filter((ticket) => !linked.has(ticket.id))
  }, [context?.linked_tickets, customerTicketsQuery.data])

  const selectConversation = useCallback((next: Conversation) => {
    if (next.id !== activeConversationId) setPendingAttachments([])
    setSelectedConversationId(next.id)
    setMobilePane('thread')
    const url = new URL(window.location.href)
    url.searchParams.set('screen', 'channels')
    url.searchParams.set('conversation', next.id)
    window.history.replaceState({}, '', url)
  }, [activeConversationId])

  function updateDraft(value: string) {
    setDraft(value)
    window.clearTimeout(typingTimer.current)
    sendTyping(activeConversationId, value.trim().length > 0)
    typingTimer.current = window.setTimeout(() => sendTyping(activeConversationId, false), 1_500)
  }

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      const command = event.metaKey || event.ctrlKey
      const target = event.target
      const isEditing =
        target instanceof Element &&
        target.matches('input, textarea, select, [contenteditable="true"]')

      if (event.altKey && !command && event.key === 'ArrowUp') {
        event.preventDefault()
        const index = conversations.findIndex((item) => item.id === activeConversationId)
        const next = conversations[index + 1]
        if (next) selectConversation(next)
        return
      }
      if (event.altKey && !command && event.key === 'ArrowDown') {
        event.preventDefault()
        const index = conversations.findIndex((item) => item.id === activeConversationId)
        const previous = conversations[index - 1]
        if (previous) selectConversation(previous)
        return
      }
      if (event.altKey && event.shiftKey && event.key.toLowerCase() === 'i') {
        event.preventDefault()
        if (!intelliAssignMutation.isPending) intelliAssignMutation.mutate()
        return
      }
      if (command && event.altKey && event.key === 'Enter') {
        event.preventDefault()
        if (!sendAndResolveMutation.isPending) sendAndResolveMutation.mutate()
        return
      }
      if (command && event.shiftKey && event.key.toLowerCase() === 'u') {
        event.preventDefault()
        savedViewSelect.current?.focus()
        return
      }
      if (command && event.shiftKey && (event.key === "'" || event.key === '"')) {
        event.preventDefault()
        setComposerMode((current) => (current === 'reply' ? 'private' : 'reply'))
        requestAnimationFrame(() => composerInput.current?.focus())
        return
      }
      if (command && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'y') {
        event.preventDefault()
        if (!statusMutation.isPending) {
          statusMutation.mutate(
            conversation?.status === 'resolved' || conversation?.status === 'closed'
              ? 'reopen'
              : 'resolve',
          )
        }
        return
      }
      if (isEditing) return
    }

    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [
    activeConversationId,
    conversation?.status,
    conversations,
    intelliAssignMutation,
    selectConversation,
    sendAndResolveMutation,
    statusMutation,
  ])

  if (featureQuery.isLoading) {
    return (
      <main className="omnichat-gate" aria-busy="true">
        <LoaderCircle className="spin" size={22} />
        <span>Loading Omnichat workspace</span>
      </main>
    )
  }

  if (!canUseWorkspace) {
    return (
      <main className="omnichat-gate">
        <MessageCircle size={28} />
        <h1>Omnichat pilot is not enabled</h1>
        <p>This workspace is available only to approved users, roles, and markets.</p>
        <button type="button" onClick={() => onNavigate('command')}>
          <ArrowLeft size={16} /> Back to Dashboard
        </button>
      </main>
    )
  }

  return (
    <div className={`omnichat-shell mobile-pane-${mobilePane}`}>
      <aside className="omnichat-rail" aria-label="Omnichat navigation">
        <button className="omnichat-logo" type="button" onClick={() => onNavigate('command')} title="Omni home">
          O
        </button>
        <nav>
          <button className="active" type="button" title="Team Inbox" aria-label="Team Inbox">
            <Inbox size={19} />
          </button>
          <button type="button" title="Contacts" aria-label="Contacts" onClick={() => onNavigate('customers')}>
            <Users size={19} />
          </button>
          <button type="button" title="Solutions" aria-label="Solutions" onClick={() => onNavigate('knowledge')}>
            <BookOpen size={19} />
          </button>
          <button type="button" title="AI Agents" aria-label="AI Agents" onClick={() => onNavigate('automation')}>
            <Bot size={19} />
          </button>
          <button type="button" title="Analytics" aria-label="Analytics" onClick={() => onNavigate('analytics')}>
            <LayoutDashboard size={19} />
          </button>
        </nav>
        <div className="omnichat-rail-bottom">
          <span className={`omnichat-presence ${connectionStatus}`} title={`Realtime ${connectionStatus}`} />
          <button type="button" title="Settings" aria-label="Settings" onClick={() => onNavigate('admin')}>
            <Settings size={19} />
          </button>
          <button type="button" className="omnichat-avatar" title={session.user.name} aria-label={session.user.name}>
            {initials(session.user.name)}
          </button>
        </div>
      </aside>

      <section className="omnichat-queue" aria-label="Conversation queue">
        <header className="omnichat-queue-head">
          <div>
            <span>OMNICHAT</span>
            <h1>Team Inbox</h1>
          </div>
          <div className="omnichat-queue-head-actions"><button type="button" className="omnichat-icon-button" aria-label="Keyboard shortcuts" title="Keyboard shortcuts" onClick={() => setShortcutsOpen(true)}><Keyboard size={17} /></button><button type="button" className="omnichat-icon-button" aria-label="New conversation" title="New conversation" onClick={() => setNewConversationOpen(true)}>
            <Plus size={18} />
          </button></div>
        </header>
        <div className="omnichat-view-row">
          <select ref={savedViewSelect} value={selectedViewId} onChange={(event) => setSelectedViewId(event.target.value)} aria-label="Saved conversation view">
            <option value="">All conversations</option>
            {viewsQuery.data?.map((view) => (
              <option value={view.id} key={view.id}>{view.name}</option>
            ))}
          </select>
          <button type="button" className="omnichat-icon-button" title="Notifications" aria-label="Notifications">
            <Bell size={17} />
          </button>
        </div>
        <label className="omnichat-search">
          <Search size={16} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search conversations" />
          {search ? <button type="button" onClick={() => setSearch('')} aria-label="Clear search"><X size={14} /></button> : null}
        </label>
        <div className="omnichat-filter-tabs" role="tablist" aria-label="Conversation status">
          {[
            ['open,pending', 'Open'],
            ['resolved,closed', 'Resolved'],
            ['', 'All'],
          ].map(([value, label]) => (
            <button key={label} type="button" role="tab" aria-selected={statusFilter === value} className={statusFilter === value ? 'active' : ''} onClick={() => setStatusFilter(value)}>
              {label}
            </button>
          ))}
        </div>
        {selectedView ? <div className="omnichat-active-view"><Sparkles size={13} /> {selectedView.name}</div> : null}
        <div className="omnichat-conversation-list">
          {conversationsQuery.isLoading ? (
            <div className="omnichat-list-state"><LoaderCircle className="spin" size={20} /> Loading conversations</div>
          ) : conversationsQuery.isError ? (
            <div className="omnichat-list-state error">{conversationsQuery.error.message}</div>
          ) : conversations.length === 0 ? (
            <div className="omnichat-list-state">
              <MessageCircle size={24} />
              <strong>No conversations in this view</strong>
              <button type="button" onClick={() => setNewConversationOpen(true)}>Start conversation</button>
            </div>
          ) : conversations.map((item) => (
            <button type="button" className={`omnichat-conversation-row ${item.id === activeConversationId ? 'active' : ''}`} key={item.id} onClick={() => selectConversation(item)}>
              <span className="omnichat-customer-avatar">{initials(item.customer_name || item.customer_email)}</span>
              <span className="omnichat-conversation-copy">
                <span><strong>{item.customer_name || item.customer_email}</strong><time>{formatActivityTime(item.last_message_at)}</time></span>
                <b>{item.subject || readableChannel(item.channel)}</b>
                <small>{item.latest_message || 'No messages yet'}</small>
                <em>{readableChannel(item.channel)}{item.group_name ? ` · ${item.group_name}` : ''}</em>
              </span>
              {item.unread_count ? <span className="omnichat-unread">{item.unread_count}</span> : null}
            </button>
          ))}
        </div>
        <footer className="omnichat-queue-footer">
          <select value={session.market.id} onChange={(event) => onSwitchMarket(event.target.value)} aria-label="Market">
            {session.available_markets.map((market) => <option value={market.id} key={market.id}>{market.code} · {market.name}</option>)}
          </select>
          <button type="button" onClick={onSignOut}>Sign out</button>
        </footer>
      </section>

      <main className="omnichat-thread" aria-label="Active conversation">
        {!conversation ? (
          <div className="omnichat-empty-thread">
            <MessageCircle size={36} />
            <h2>Select a conversation</h2>
            <p>Choose work from Team Inbox or start a new conversation.</p>
          </div>
        ) : (
          <>
            <header className="omnichat-thread-head">
              <button className="omnichat-mobile-back" type="button" onClick={() => setMobilePane('queue')} aria-label="Back to queue"><ArrowLeft size={19} /></button>
              <span className="omnichat-customer-avatar large">{initials(conversation.customer_name || conversation.customer_email)}</span>
              <div>
                <h2>{conversation.customer_name || conversation.customer_email}</h2>
                <span>{conversation.subject || conversation.public_id} · {readableChannel(conversation.channel)}</span>
              </div>
              <div className="omnichat-thread-actions">
                <select value={conversation.assigned_group_id ?? ''} onChange={(event) => assignmentMutation.mutate({ groupId: event.target.value })} aria-label="Assign group" disabled={assignmentMutation.isPending}>
                  <option value="">Unassigned group</option>
                  {groupsQuery.data?.filter((group) => group.active).map((group) => <option value={group.id} key={group.id}>{group.name}</option>)}
                </select>
                <select value={conversation.assignee_id ?? ''} onChange={(event) => assignmentMutation.mutate({ assigneeId: event.target.value })} aria-label="Assign agent" disabled={assignmentMutation.isPending}>
                  <option value="">Unassigned agent</option>
                  {usersQuery.data?.filter((user) => user.active && user.market_ids.includes(session.market.id)).map((user) => <option value={user.id} key={user.id}>{user.name}</option>)}
                </select>
                <button type="button" className="omnichat-icon-button" disabled={intelliAssignMutation.isPending} onClick={() => intelliAssignMutation.mutate()} aria-label="IntelliAssign" title="IntelliAssign (Option+Shift+I)"><Sparkles size={17} /></button>
                <button type="button" className="omnichat-status-button" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate(conversation.status === 'resolved' || conversation.status === 'closed' ? 'reopen' : 'resolve')} title="Resolve or reopen (Cmd/Ctrl+Y)">
                  <Check size={16} /> {conversation.status === 'resolved' || conversation.status === 'closed' ? 'Reopen' : 'Resolve'}
                </button>
                <button type="button" className="omnichat-icon-button context-toggle" onClick={() => setMobilePane('context')} aria-label="Customer context"><PanelRight size={18} /></button>
                <button type="button" className="omnichat-icon-button" aria-label="More actions"><MoreHorizontal size={19} /></button>
              </div>
            </header>
            <section className="omnichat-message-stream" aria-live="polite">
              {messagesQuery.isLoading ? <div className="omnichat-list-state"><LoaderCircle className="spin" size={20} /> Loading messages</div> : null}
              {messages.map((message, index) => {
                const previous = messages[index - 1]
                const showDay = !previous || new Date(previous.sent_at).toDateString() !== new Date(message.sent_at).toDateString()
                const messageAttachments = context?.attachments.filter(
                  (attachment) => attachment.message_id === message.id && !attachment.deleted_at,
                ) ?? []
                return (
                  <div key={message.id}>
                    {showDay ? <div className="omnichat-day-divider"><span>{new Date(message.sent_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span></div> : null}
                    <article className={`omnichat-message ${message.sender_type === 'customer' ? 'customer' : 'agent'} ${message.visibility === 'private' ? 'private' : ''}`}>
                      <span className="omnichat-message-avatar">{initials(message.sender_name || message.sender_type)}</span>
                      <div>
                        <header><strong>{message.sender_name || message.sender_type}</strong><time>{new Date(message.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></header>
                        <p>{message.body}</p>
                        {messageAttachments.length ? <div className="omnichat-message-attachments">
                          {messageAttachments.map((attachment) => (
                            <a
                              key={attachment.id}
                              href={conversationAttachmentDownloadUrl(message.conversation_id, attachment.id)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <Paperclip size={13} />
                              <span>{attachment.filename}</span>
                              <small>{Math.max(1, Math.ceil(attachment.size_bytes / 1024))} KB</small>
                            </a>
                          ))}
                        </div> : null}
                        <footer>{deliveryLabel(message.delivery_state)}</footer>
                      </div>
                    </article>
                  </div>
                )
              })}
              {typingActors.length ? <div className="omnichat-typing">{typingActors.map((actor) => actor.userName).join(', ')} typing...</div> : null}
            </section>
            <section className={`omnichat-composer ${composerMode}`}>
              <div className="omnichat-composer-tabs">
                <button type="button" className={composerMode === 'reply' ? 'active' : ''} onClick={() => setComposerMode('reply')}>Reply</button>
                <button type="button" className={composerMode === 'private' ? 'active' : ''} onClick={() => setComposerMode('private')}>Private note</button>
              </div>
              <textarea ref={composerInput} value={draft} onChange={(event) => updateDraft(event.target.value)} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key === 'Enter') { event.preventDefault(); sendMutation.mutate() } }} placeholder={composerMode === 'private' ? 'Add a note visible only to your team' : 'Reply to the customer'} aria-label={composerMode === 'private' ? 'Private note' : 'Customer reply'} />
              {pendingAttachments.length ? <div className="omnichat-pending-attachments">
                {pendingAttachments.map((attachment) => (
                  <span key={attachment.id}>
                    <Paperclip size={13} />
                    <b>{attachment.filename}</b>
                    <button
                      type="button"
                      onClick={() => setPendingAttachments((current) => current.filter((item) => item.id !== attachment.id))}
                      aria-label={`Remove ${attachment.filename}`}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div> : null}
              <div className="omnichat-composer-tools">
                <div>
                  <select aria-label="Insert canned response" value="" onChange={(event) => { const macro = macrosQuery.data?.find((item) => item.id === event.target.value); if (macro) setDraft((current) => `${current}${current ? '\n\n' : ''}${macro.body}`) }}>
                    <option value="">Canned response</option>
                    {macrosQuery.data?.filter((macro) => macro.active).map((macro) => <option value={macro.id} key={macro.id}>{macro.name}</option>)}
                  </select>
                  <input
                    ref={attachmentInput}
                    className="omnichat-file-input"
                    type="file"
                    aria-label="Choose conversation attachment"
                    onChange={(event) => {
                      const file = event.target.files?.[0]
                      if (file) attachmentMutation.mutate(file)
                      event.target.value = ''
                    }}
                  />
                  <button
                    type="button"
                    title="Attach a file"
                    aria-label="Attach a file"
                    disabled={attachmentMutation.isPending || !online}
                    onClick={() => attachmentInput.current?.click()}
                  >
                    {attachmentMutation.isPending ? <LoaderCircle className="spin" size={17} /> : <Paperclip size={17} />}
                  </button>
                  <button type="button" aria-label="Emoji"><Smile size={17} /></button>
                </div>
                <button type="button" className="omnichat-send" disabled={(!draft.trim() && pendingAttachments.length === 0) || sendMutation.isPending || !online} onClick={() => sendMutation.mutate()}>
                  {sendMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />} Send
                </button>
              </div>
            </section>
          </>
        )}
      </main>

      <aside className="omnichat-context" aria-label="Customer context">
        <header>
          <button className="omnichat-mobile-back" type="button" onClick={() => setMobilePane('thread')} aria-label="Back to conversation"><ArrowLeft size={19} /></button>
          <h2>Customer details</h2>
          <button type="button" className="omnichat-icon-button" aria-label="More customer actions"><MoreHorizontal size={18} /></button>
        </header>
        {!conversation ? <div className="omnichat-list-state">Select a conversation to view customer context.</div> : contextQuery.isLoading ? (
          <div className="omnichat-list-state"><LoaderCircle className="spin" size={20} /> Loading customer context</div>
        ) : contextQuery.isError ? (
          <div className="omnichat-list-state error">
            <strong>Customer context is unavailable</strong>
            <span>{contextQuery.error.message}</span>
            <button type="button" onClick={() => void contextQuery.refetch()}>Retry</button>
          </div>
        ) : !context ? (
          <div className="omnichat-list-state error">Customer context was not returned by the API.</div>
        ) : (
          <div className="omnichat-context-scroll">
            <section className="omnichat-customer-summary">
              <span className="omnichat-customer-avatar xlarge">{initials(context.customer.name)}</span>
              <h3>{context.customer.name}</h3>
              <a href={`mailto:${context.customer.email}`}>{context.customer.email}</a>
              <div><span>{context.customer.sentiment}</span>{(context.customer.tags ?? []).map((tag) => <span key={tag}>{tag}</span>)}</div>
            </section>
            <section className="omnichat-context-section">
              <button type="button" onClick={() => setContextExpanded((current) => ({ ...current, details: !current.details }))}><span><CircleUserRound size={16} /> Conversation properties</span><ChevronDown className={contextExpanded.details ? 'open' : ''} size={16} /></button>
              {contextExpanded.details ? <div className="omnichat-property-list">
                <label>Topic<select value={conversation?.topic_id ?? ''} onChange={(event) => topicMutation.mutate(event.target.value)} disabled={!conversation || topicMutation.isPending}><option value="">No topic</option>{topicsQuery.data?.filter((topic) => topic.active).map((topic) => <option value={topic.id} key={topic.id}>{topic.name}</option>)}</select></label>
                <div><span>Status</span><strong>{conversation?.status}</strong></div>
                <div><span>Priority</span><strong>{conversation?.priority}</strong></div>
                <div><span>Case</span><strong>{context.case.public_id}</strong></div>
                <div><span>Location</span><strong>{context.customer.location || 'Not provided'}</strong></div>
              </div> : null}
            </section>
            <section className="omnichat-context-section">
              <button type="button" onClick={() => setContextExpanded((current) => ({ ...current, history: !current.history }))}><span><Clock3 size={16} /> Conversation history</span><ChevronDown className={contextExpanded.history ? 'open' : ''} size={16} /></button>
              {contextExpanded.history ? <div className="omnichat-history-list">{context.customer_history.length ? context.customer_history.map((item) => <button type="button" key={item.id} onClick={() => selectConversation(item)}><span>{item.subject || item.public_id}</span><small>{readableChannel(item.channel)} · {formatActivityTime(item.last_message_at)}</small></button>) : <p>No earlier conversations.</p>}</div> : null}
            </section>
            <section className="omnichat-context-section">
              <button type="button" onClick={() => setContextExpanded((current) => ({ ...current, tickets: !current.tickets }))}><span><TicketCheck size={16} /> Linked tickets</span><ChevronDown className={contextExpanded.tickets ? 'open' : ''} size={16} /></button>
              {contextExpanded.tickets ? <div className="omnichat-ticket-links">
                {context.linked_tickets.map((ticket) => <button type="button" key={ticket.id} onClick={() => { window.location.href = `?screen=inbox&conversation=${encodeURIComponent(ticket.id)}` }}><strong>{ticket.public_id}</strong><span>{ticket.subject}</span><small>{ticket.status}</small></button>)}
                <label><Link2 size={15} /><select aria-label="Link a ticket" value="" onChange={(event) => event.target.value && linkMutation.mutate(event.target.value)} disabled={!candidateTickets.length || linkMutation.isPending}><option value="">Link a ticket</option>{candidateTickets.map((ticket) => <option value={ticket.id} key={ticket.id}>{ticket.public_id} · {ticket.subject}</option>)}</select></label>
              </div> : null}
            </section>
            <section className="omnichat-context-section">
              <button type="button" onClick={() => setContextExpanded((current) => ({ ...current, attachments: !current.attachments }))}><span><Paperclip size={16} /> Attachments</span><ChevronDown className={contextExpanded.attachments ? 'open' : ''} size={16} /></button>
              {contextExpanded.attachments ? <div className="omnichat-context-attachments">
                {context.attachments.filter((attachment) => !attachment.deleted_at).map((attachment) => (
                  <a
                    key={attachment.id}
                    href={conversationAttachmentDownloadUrl(context.conversation.id, attachment.id)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Paperclip size={14} />
                    <span>{attachment.filename}</span>
                    <small>{Math.max(1, Math.ceil(attachment.size_bytes / 1024))} KB</small>
                  </a>
                ))}
                {!context.attachments.some((attachment) => !attachment.deleted_at) ? <p>No attachments.</p> : null}
              </div> : null}
            </section>
            <section className="omnichat-context-section compact">
              <div className="omnichat-context-action"><UserRoundCheck size={16} /><span>{context.participants.length} participants</span></div>
              <div className="omnichat-context-action"><TicketCheck size={16} /><span>{context.case.ticket_count} case tickets</span></div>
            </section>
          </div>
        )}
      </aside>

      {notice ? <div className="omnichat-toast" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Dismiss"><X size={14} /></button></div> : null}

      {shortcutsOpen ? (
        <div className="omnichat-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setShortcutsOpen(false) }}>
          <section className="omnichat-dialog omnichat-shortcuts" role="dialog" aria-modal="true" aria-labelledby="omnichat-shortcuts-title">
            <header><div><span>KEYBOARD</span><h2 id="omnichat-shortcuts-title">Keyboard shortcuts</h2></div><button type="button" onClick={() => setShortcutsOpen(false)} aria-label="Close"><X size={18} /></button></header>
            <dl>
              <div><dt>Resolve or reopen</dt><dd><kbd>Cmd/Ctrl</kbd><kbd>Y</kbd></dd></div>
              <div><dt>Send and resolve</dt><dd><kbd>Cmd/Ctrl</kbd><kbd>Option</kbd><kbd>Enter</kbd></dd></div>
              <div><dt>Next conversation</dt><dd><kbd>Option</kbd><kbd>Up</kbd></dd></div>
              <div><dt>Previous conversation</dt><dd><kbd>Option</kbd><kbd>Down</kbd></dd></div>
              <div><dt>IntelliAssign</dt><dd><kbd>Option</kbd><kbd>Shift</kbd><kbd>I</kbd></dd></div>
              <div><dt>Reply or private note</dt><dd><kbd>Cmd/Ctrl</kbd><kbd>Shift</kbd><kbd>'</kbd></dd></div>
              <div><dt>Open saved views</dt><dd><kbd>Cmd/Ctrl</kbd><kbd>Shift</kbd><kbd>U</kbd></dd></div>
            </dl>
          </section>
        </div>
      ) : null}

      {newConversationOpen ? (
        <div className="omnichat-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setNewConversationOpen(false) }}>
          <form className="omnichat-dialog" onSubmit={(event) => { event.preventDefault(); createMutation.mutate() }}>
            <header><div><span>NEW</span><h2>Start a conversation</h2></div><button type="button" onClick={() => setNewConversationOpen(false)} aria-label="Close"><X size={18} /></button></header>
            <label>Customer<select required value={newConversation.customerId} onChange={(event) => setNewConversation((current) => ({ ...current, customerId: event.target.value }))}><option value="">Select customer</option>{customersQuery.data?.map((customer) => <option value={customer.id} key={customer.id}>{customer.name} · {customer.email}</option>)}</select></label>
            <label>Channel<select value={newConversation.channel} onChange={(event) => setNewConversation((current) => ({ ...current, channel: event.target.value }))}><option value="whatsapp">WhatsApp</option><option value="facebook">Facebook</option><option value="instagram">Instagram</option><option value="chat">Web chat</option><option value="sms">SMS</option></select></label>
            <label>Subject<input required value={newConversation.subject} onChange={(event) => setNewConversation((current) => ({ ...current, subject: event.target.value }))} /></label>
            <label>First message<textarea required value={newConversation.message} onChange={(event) => setNewConversation((current) => ({ ...current, message: event.target.value }))} /></label>
            <footer><button type="button" onClick={() => setNewConversationOpen(false)}>Cancel</button><button type="submit" disabled={createMutation.isPending}>{createMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />} Create</button></footer>
          </form>
        </div>
      ) : null}
    </div>
  )
}

export default OmnichatWorkspace
