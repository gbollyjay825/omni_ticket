import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Bell,
  BookmarkPlus,
  BookOpen,
  Check,
  CircleUserRound,
  ClipboardList,
  Clock3,
  Download,
  Eye,
  EyeOff,
  FileText,
  Filter,
  Inbox,
  LayoutDashboard,
  Link2,
  List,
  LoaderCircle,
  Merge,
  MessageSquareReply,
  MoreHorizontal,
  Paperclip,
  Plus,
  Search,
  Send,
  Settings,
  Sparkles,
  TableProperties,
  TicketCheck,
  Users,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import type { BackendSession } from '../../backend'
import {
  createTicket,
  createTicketTask,
  createTicketTimeEntry,
  createTicketView,
  exportTickets,
  fetchCustomers,
  fetchScenarios,
  fetchTags,
  fetchTickets,
  fetchTicketViews,
  fetchTicketWorkspace,
  fetchUsers,
  forwardTicket,
  mergeTickets,
  runTicketScenario,
  sendTicketMessage,
  setTicketWatch,
  updateTicket,
  uploadTicketAttachment,
  type Ticket,
  type TicketUpdate,
} from './api'
import './ticket-workspace.css'

interface TicketWorkspaceProps {
  session: BackendSession
  online: boolean
  onNavigate: (screen: string) => void
  onSignOut: () => void
}

type TicketLayout = 'card' | 'table'
type ComposerMode = 'reply' | 'note'
type DetailPanel = 'properties' | 'activity' | 'links' | 'tasks' | 'time' | 'suggestions'

const PAGE_SIZE = 30

function initials(value: string) {
  return value
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function formatRelative(value?: string) {
  if (!value) return 'Unknown time'
  const elapsed = Date.now() - new Date(value).getTime()
  if (elapsed < 60_000) return 'now'
  if (elapsed < 3_600_000) return `${Math.floor(elapsed / 60_000)}m ago`
  if (elapsed < 86_400_000) return `${Math.floor(elapsed / 3_600_000)}h ago`
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function readable(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function TicketWorkspace({ session, online, onNavigate, onSignOut }: TicketWorkspaceProps) {
  const queryClient = useQueryClient()
  const initialTicketId = new URLSearchParams(window.location.search).get('conversation') ?? ''
  const [ticketId, setTicketId] = useState(initialTicketId)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [channel, setChannel] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [team, setTeam] = useState('')
  const [customerId, setCustomerId] = useState('')
  const [createdPeriod, setCreatedPeriod] = useState<'' | 'today' | '7d' | '30d'>('')
  const [tag, setTag] = useState('')
  const [selectedViewId, setSelectedViewId] = useState('')
  const [sortBy, setSortBy] = useState<'updated_at' | 'created_at' | 'priority'>('updated_at')
  const [layout, setLayout] = useState<TicketLayout>('card')
  const [offset, setOffset] = useState(0)
  const [filtersOpen, setFiltersOpen] = useState(() => window.innerWidth > 900)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [composerMode, setComposerMode] = useState<ComposerMode>('reply')
  const [draft, setDraft] = useState('')
  const [notice, setNotice] = useState('')
  const [detailPanel, setDetailPanel] = useState<DetailPanel>('properties')
  const [timeDialogOpen, setTimeDialogOpen] = useState(false)
  const [timeMinutes, setTimeMinutes] = useState('15')
  const [timeNote, setTimeNote] = useState('')
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false)
  const [mergeSourceId, setMergeSourceId] = useState('')
  const [forwardDialogOpen, setForwardDialogOpen] = useState(false)
  const [forwardEmail, setForwardEmail] = useState('')
  const [forwardSubject, setForwardSubject] = useState('')
  const [forwardBody, setForwardBody] = useState('')
  const [taskDialogOpen, setTaskDialogOpen] = useState(false)
  const [taskLabel, setTaskLabel] = useState('')
  const [newDialogOpen, setNewDialogOpen] = useState(false)
  const [newCustomerId, setNewCustomerId] = useState('')
  const [newSubject, setNewSubject] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [newChannel, setNewChannel] = useState<Ticket['channel']>('email')
  const [newPriority, setNewPriority] = useState<Ticket['priority']>('normal')
  const [saveViewOpen, setSaveViewOpen] = useState(false)
  const [viewName, setViewName] = useState('')
  const [viewShared, setViewShared] = useState(false)
  const [scenarioId, setScenarioId] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const handlePopState = () => {
      setTicketId(new URLSearchParams(window.location.search).get('conversation') ?? '')
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const ticketsQuery = useQuery({
    queryKey: [
      'ticket-queue',
      session.market.id,
      query,
      selectedViewId,
      status,
      priority,
      channel,
      assigneeId,
      team,
      customerId,
      createdPeriod,
      tag,
      sortBy,
      offset,
    ],
    queryFn: () =>
      fetchTickets(session, {
        viewId: selectedViewId || undefined,
        query: query.trim().length > 1 ? query.trim() : undefined,
        status: status || undefined,
        priority: (priority || undefined) as Ticket['priority'] | undefined,
        channel: (channel || undefined) as Ticket['channel'] | undefined,
        assigneeId: assigneeId || undefined,
        team: team || undefined,
        customerId: customerId || undefined,
        createdPeriod: createdPeriod || undefined,
        tag: tag || undefined,
        sortBy,
        limit: PAGE_SIZE,
        offset,
      }),
    refetchInterval: 30_000,
  })
  const customersQuery = useQuery({
    queryKey: ['ticket-customers', session.market.id],
    queryFn: () => fetchCustomers(session),
  })
  const usersQuery = useQuery({
    queryKey: ['ticket-users', session.market.id],
    queryFn: () => fetchUsers(session),
  })
  const scenariosQuery = useQuery({
    queryKey: ['ticket-scenarios', session.market.id],
    queryFn: () => fetchScenarios(session),
  })
  const viewsQuery = useQuery({
    queryKey: ['ticket-views', session.market.id, session.user.id],
    queryFn: () => fetchTicketViews(session),
  })
  const tagsQuery = useQuery({
    queryKey: ['ticket-tags', session.market.id],
    queryFn: () => fetchTags(session),
  })
  const workspaceQuery = useQuery({
    queryKey: ['ticket-workspace', session.market.id, ticketId],
    queryFn: () => fetchTicketWorkspace(session, ticketId),
    enabled: Boolean(ticketId),
    refetchInterval: 30_000,
  })

  const tickets = ticketsQuery.data?.items ?? []
  const total = ticketsQuery.data?.total ?? 0
  const customerById = useMemo(
    () => new Map((customersQuery.data ?? []).map((customer) => [customer.id, customer])),
    [customersQuery.data],
  )
  const users = usersQuery.data?.filter(
    (user) => user.active && user.market_ids.includes(session.market.id),
  ) ?? []
  const teams = Array.from(new Set(tickets.map((ticket) => ticket.team).filter(Boolean)))
  const workspace = workspaceQuery.data
  const timeline = workspace?.timeline ?? []
  const attachments = workspace?.attachments ?? []
  const linkedTickets = workspace?.linked_tickets ?? []
  const handoffs = workspace?.handoffs ?? []
  const tasks = workspace?.tasks ?? []
  const timeEntries = workspace?.time_entries ?? []
  const knowledgeSuggestions = workspace?.suggestions.knowledge ?? []
  const macroSuggestions = workspace?.suggestions.macros ?? []

  async function refreshAll() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['ticket-queue', session.market.id] }),
      queryClient.invalidateQueries({ queryKey: ['ticket-workspace', session.market.id, ticketId] }),
    ])
  }

  function openTicket(nextTicketId: string, replace = false) {
    setTicketId(nextTicketId)
    setSelectedIds([])
    const url = new URL(window.location.href)
    url.searchParams.set('screen', 'inbox')
    url.searchParams.set('conversation', nextTicketId)
    window.history[replace ? 'replaceState' : 'pushState']({}, '', url)
  }

  function closeTicket() {
    setTicketId('')
    const url = new URL(window.location.href)
    url.searchParams.set('screen', 'inbox')
    url.searchParams.delete('conversation')
    window.history.pushState({}, '', url)
  }

  const patchMutation = useMutation({
    mutationFn: ({ ticket, patch }: { ticket: Ticket; patch: TicketUpdate }) =>
      updateTicket(session, ticket.id, { expected_version: ticket.version, ...patch }),
    onSuccess: () => void refreshAll(),
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Ticket update failed.'),
  })
  const replyMutation = useMutation({
    mutationFn: () => {
      if (!workspace || !draft.trim()) throw new Error('Enter a message first.')
      return sendTicketMessage(session, workspace.ticket.id, {
        actor: session.user.name,
        channel: workspace.ticket.channel,
        body: draft.trim(),
        public: composerMode === 'reply',
        idempotency_key: crypto.randomUUID(),
      })
    },
    onSuccess: () => {
      setDraft('')
      setNotice(composerMode === 'reply' ? 'Reply queued for delivery.' : 'Private note added.')
      void refreshAll()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Message failed.'),
  })
  const watchMutation = useMutation({
    mutationFn: () => {
      if (!workspace) throw new Error('Ticket not loaded.')
      return setTicketWatch(session, workspace.ticket.id, !workspace.watching)
    },
    onSuccess: () => void refreshAll(),
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Watch update failed.'),
  })
  const timeMutation = useMutation({
    mutationFn: () => {
      if (!workspace) throw new Error('Ticket not loaded.')
      return createTicketTimeEntry(session, workspace.ticket.id, {
        minutes: Number(timeMinutes),
        note: timeNote.trim(),
        billable: false,
      })
    },
    onSuccess: () => {
      setTimeDialogOpen(false)
      setTimeNote('')
      setNotice('Time entry added.')
      void refreshAll()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Time entry failed.'),
  })
  const scenarioMutation = useMutation({
    mutationFn: () => {
      if (!workspace || !scenarioId) throw new Error('Select a scenario.')
      return runTicketScenario(session, workspace.ticket.id, scenarioId)
    },
    onSuccess: () => {
      setNotice('Scenario applied.')
      void refreshAll()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Scenario failed.'),
  })
  const mergeMutation = useMutation({
    mutationFn: () => {
      if (!workspace || !mergeSourceId) throw new Error('Select a source ticket.')
      return mergeTickets(session, workspace.ticket.id, mergeSourceId)
    },
    onSuccess: () => {
      setMergeDialogOpen(false)
      setMergeSourceId('')
      setNotice('Tickets merged.')
      void refreshAll()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Merge failed.'),
  })
  const forwardMutation = useMutation({
    mutationFn: () => {
      if (!workspace) throw new Error('Ticket not loaded.')
      return forwardTicket(session, workspace.ticket.id, {
        expected_version: workspace.ticket.version,
        to_email: forwardEmail.trim(),
        subject: forwardSubject.trim(),
        body: forwardBody.trim(),
        idempotency_key: crypto.randomUUID(),
      })
    },
    onSuccess: () => {
      setForwardDialogOpen(false)
      setForwardEmail('')
      setForwardSubject('')
      setForwardBody('')
      setNotice('Forward queued for email delivery.')
      void refreshAll()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Forward failed.'),
  })
  const taskMutation = useMutation({
    mutationFn: () => {
      if (!workspace) throw new Error('Ticket not loaded.')
      return createTicketTask(session, workspace.ticket.id, {
        expected_version: workspace.ticket.version,
        label: taskLabel.trim(),
      })
    },
    onSuccess: () => {
      setTaskDialogOpen(false)
      setTaskLabel('')
      setDetailPanel('tasks')
      setNotice('Child task created.')
      void refreshAll()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Task creation failed.'),
  })
  const newTicketMutation = useMutation({
    mutationFn: () =>
      createTicket(session, {
        customer_id: newCustomerId,
        subject: newSubject.trim(),
        description: newDescription.trim(),
        channel: newChannel,
        priority: newPriority,
      }),
    onSuccess: (ticket) => {
      setNewDialogOpen(false)
      setNewCustomerId('')
      setNewSubject('')
      setNewDescription('')
      setNotice(`${ticket.public_id} created.`)
      void refreshAll()
      openTicket(ticket.id)
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Ticket creation failed.'),
  })
  const saveViewMutation = useMutation({
    mutationFn: () => {
      const filters = Object.fromEntries(
        Object.entries({
          status,
          priority,
          channel,
          assignee_id: assigneeId,
          team,
          customer_id: customerId,
          created_period: createdPeriod,
          tag,
        }).filter(([, value]) => Boolean(value)),
      )
      return createTicketView(session, {
        name: viewName.trim(),
        filters,
        sort_by: sortBy,
        sort_order: 'desc',
        position: 100,
        shared: viewShared,
      })
    },
    onSuccess: (view) => {
      setSaveViewOpen(false)
      setViewName('')
      setViewShared(false)
      setSelectedViewId(view.id)
      setNotice(`Saved view “${view.name}” created.`)
      void queryClient.invalidateQueries({ queryKey: ['ticket-views', session.market.id] })
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Saved view creation failed.'),
  })
  const attachmentMutation = useMutation({
    mutationFn: (file: File) => {
      if (!workspace) throw new Error('Ticket not loaded.')
      return uploadTicketAttachment(session, workspace.ticket.id, file)
    },
    onSuccess: () => {
      setNotice('Attachment uploaded for scanning.')
      void refreshAll()
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Upload failed.'),
  })

  async function bulkPatch(patch: TicketUpdate) {
    const chosen = tickets.filter((ticket) => selectedIds.includes(ticket.id))
    try {
      await Promise.all(
        chosen.map((ticket) =>
          updateTicket(session, ticket.id, { expected_version: ticket.version, ...patch }),
        ),
      )
      setSelectedIds([])
      await refreshAll()
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Bulk update failed.')
    }
  }

  async function downloadTicketExport() {
    try {
      const report = await exportTickets(session)
      const href = URL.createObjectURL(new Blob([report.content], { type: report.contentType }))
      const anchor = document.createElement('a')
      anchor.href = href
      anchor.download = report.filename
      anchor.click()
      URL.revokeObjectURL(href)
      setNotice('Ticket export downloaded.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Ticket export failed.')
    }
  }

  const activeFilters = [
    query,
    selectedViewId,
    status,
    priority,
    channel,
    assigneeId,
    team,
    customerId,
    createdPeriod,
    tag,
  ].filter(Boolean).length

  return (
    <div className="ticket-workspace-shell">
      <aside className="ticket-rail" aria-label="Ticket navigation">
        <button className="ticket-logo" type="button" onClick={() => onNavigate('command')} title="Omni home">O</button>
        <nav>
          <button type="button" title="Dashboard" aria-label="Dashboard" onClick={() => onNavigate('command')}><LayoutDashboard size={19} /></button>
          <button className="active" type="button" title="Tickets" aria-label="Tickets"><Inbox size={19} /></button>
          <button type="button" title="Omnichat" aria-label="Omnichat" onClick={() => onNavigate('channels')}><MessageSquareReply size={19} /></button>
          <button type="button" title="Contacts" aria-label="Contacts" onClick={() => onNavigate('customers')}><Users size={19} /></button>
          <button type="button" title="Solutions" aria-label="Solutions" onClick={() => onNavigate('knowledge')}><BookOpen size={19} /></button>
        </nav>
        <div className="ticket-rail-bottom">
          <span className={`ticket-online ${online ? 'connected' : ''}`} title={online ? 'Online' : 'Offline'} />
          <button type="button" title="Settings" aria-label="Settings" onClick={() => onNavigate('admin')}><Settings size={19} /></button>
          <button className="ticket-user" type="button" title={session.user.name} aria-label={session.user.name}>{initials(session.user.name)}</button>
        </div>
      </aside>

      {ticketId ? (
        <main className="ticket-detail-page" aria-label="Ticket detail">
          {workspaceQuery.isLoading ? <div className="ticket-loading"><LoaderCircle className="spin" size={22} /> Loading ticket</div> : null}
          {workspaceQuery.isError ? <div className="ticket-loading error">{workspaceQuery.error.message}</div> : null}
          {workspace ? (
            <>
              <header className="ticket-detail-head">
                <button type="button" className="ticket-icon-button" onClick={closeTicket} aria-label="Back to tickets"><ArrowLeft size={18} /></button>
                <div><span>{workspace.ticket.public_id}</span><h1>{workspace.ticket.subject}</h1></div>
                <div className="ticket-detail-nav">
                  <button type="button" disabled={!workspace.previous_ticket_id} onClick={() => workspace.previous_ticket_id && openTicket(workspace.previous_ticket_id, true)} aria-label="Previous ticket"><ArrowLeft size={17} /></button>
                  <button type="button" disabled={!workspace.next_ticket_id} onClick={() => workspace.next_ticket_id && openTicket(workspace.next_ticket_id, true)} aria-label="Next ticket"><ArrowRight size={17} /></button>
                </div>
              </header>
              <nav className="ticket-command-bar" aria-label="Ticket commands">
                <button type="button" onClick={() => { setComposerMode('reply'); document.querySelector<HTMLTextAreaElement>('.ticket-composer textarea')?.focus() }}><MessageSquareReply size={16} /> Reply</button>
                <button type="button" onClick={() => { setComposerMode('note'); document.querySelector<HTMLTextAreaElement>('.ticket-composer textarea')?.focus() }}><FileText size={16} /> Add note</button>
                <button type="button" onClick={() => { setForwardSubject(`Fwd: ${workspace.ticket.subject}`); setForwardBody(workspace.ticket.description); setForwardDialogOpen(true) }}><ArrowRight size={16} /> Forward</button>
                <button type="button" onClick={() => patchMutation.mutate({ ticket: workspace.ticket, patch: { status: ['solved', 'closed'].includes(workspace.ticket.status) ? 'open' : 'closed', notify_customer: false } })}><Check size={16} /> {['solved', 'closed'].includes(workspace.ticket.status) ? 'Reopen' : 'Close'}</button>
                <button type="button" onClick={() => setTaskDialogOpen(true)}><Plus size={16} /> Child task</button>
                <button type="button" onClick={() => setMergeDialogOpen(true)}><Merge size={16} /> Merge</button>
                <label className="ticket-scenario-control"><Sparkles size={16} /><select aria-label="Run scenario" value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}><option value="">Scenario</option>{scenariosQuery.data?.filter((item) => item.active).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
                <button type="button" disabled={!scenarioId || scenarioMutation.isPending} onClick={() => scenarioMutation.mutate()} aria-label="Apply scenario"><Check size={16} /></button>
                <span />
                <button type="button" onClick={() => watchMutation.mutate()}>{workspace.watching ? <EyeOff size={16} /> : <Eye size={16} />}{workspace.watching ? 'Unwatch' : 'Watch'}</button>
                <button type="button" disabled title="No additional ticket commands are configured" aria-label="More actions"><MoreHorizontal size={18} /></button>
              </nav>

              <div className="ticket-detail-layout">
                <section className="ticket-thread-column" aria-label="Ticket conversation">
                  <div className="ticket-requester-banner">
                    <span>{initials(workspace.customer.name)}</span>
                    <div><strong>{workspace.customer.name}</strong><a href={`mailto:${workspace.customer.email}`}>{workspace.customer.email}</a></div>
                    <small>{readable(workspace.ticket.channel)} · {formatRelative(workspace.ticket.created_at)}</small>
                  </div>
                  <article className="ticket-description">
                    <header><strong>{workspace.customer.name}</strong><time>{workspace.ticket.created_at ? new Date(workspace.ticket.created_at).toLocaleString() : 'Unknown time'}</time></header>
                    <p>{workspace.ticket.description}</p>
                  </article>
                  <div className="ticket-timeline">
                    {timeline.map((event) => (
                      <article className={event.public ? 'public' : 'private'} key={event.id}>
                        <span>{initials(event.actor || 'Omni')}</span>
                        <div><header><strong>{event.actor}</strong><time>{formatRelative(event.created_at ?? workspace.ticket.updated_at)}</time></header><p>{event.body}</p><small>{readable(event.type)} · {readable(event.channel)}</small></div>
                      </article>
                    ))}
                  </div>
                  <section className={`ticket-composer ${composerMode}`}>
                    <div><button className={composerMode === 'reply' ? 'active' : ''} type="button" onClick={() => setComposerMode('reply')}>Reply</button><button className={composerMode === 'note' ? 'active' : ''} type="button" onClick={() => setComposerMode('note')}>Private note</button></div>
                    <textarea aria-label={composerMode === 'reply' ? 'Customer reply' : 'Private note'} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={composerMode === 'reply' ? 'Reply to the customer' : 'Add a note visible only to agents'} onKeyDown={(event) => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); replyMutation.mutate() } }} />
                    <footer><div><input ref={fileInput} hidden type="file" onChange={(event) => { const file = event.target.files?.[0]; if (file) attachmentMutation.mutate(file); event.target.value = '' }} /><button type="button" onClick={() => fileInput.current?.click()} aria-label="Attach file"><Paperclip size={17} /></button><span>{attachments.length} attachment(s)</span></div><button className="ticket-send" type="button" disabled={!draft.trim() || replyMutation.isPending || !online} onClick={() => replyMutation.mutate()}>{replyMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />} Send</button></footer>
                  </section>
                </section>

                <aside className="ticket-detail-panel" aria-label="Ticket properties and apps">
                  <div className="ticket-app-tabs" role="tablist" aria-label="Ticket side panels">
                    {[
                      ['properties', TableProperties, 'Properties'],
                      ['activity', Activity, 'Activity'],
                      ['links', Link2, 'Linked tickets'],
                      ['tasks', ClipboardList, 'Tasks'],
                      ['time', Clock3, 'Time logs'],
                      ['suggestions', Sparkles, 'Suggestions'],
                    ].map(([id, Icon, label]) => <button key={String(id)} type="button" role="tab" aria-selected={detailPanel === id} className={detailPanel === id ? 'active' : ''} onClick={() => setDetailPanel(id as DetailPanel)} title={String(label)} aria-label={String(label)}><Icon size={18} /></button>)}
                  </div>
                  <div className="ticket-detail-panel-content">
                    {detailPanel === 'properties' ? <>
                      <header><span>PROPERTIES</span><h2>Ticket fields</h2></header>
                      <label>Status<select value={workspace.ticket.status} onChange={(event) => patchMutation.mutate({ ticket: workspace.ticket, patch: { status: event.target.value as Ticket['status'] } })}><option value="open">Open</option><option value="pending">Pending</option><option value="waiting">Waiting</option><option value="solved">Solved</option><option value="closed">Closed</option></select></label>
                      <label>Priority<select value={workspace.ticket.priority} onChange={(event) => patchMutation.mutate({ ticket: workspace.ticket, patch: { priority: event.target.value as Ticket['priority'] } })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label>
                      <label>Agent<select value={workspace.ticket.assignee_id ?? ''} onChange={(event) => patchMutation.mutate({ ticket: workspace.ticket, patch: { assignee_id: event.target.value || null } })}><option value="">Unassigned</option>{users.map((user) => <option value={user.id} key={user.id}>{user.name}</option>)}</select></label>
                      <div className="ticket-property-readonly"><span>Group</span><strong>{workspace.ticket.team}</strong></div>
                      <div className="ticket-property-readonly"><span>Source</span><strong>{readable(workspace.ticket.channel)}</strong></div>
                      <div className="ticket-property-readonly"><span>SLA</span><strong>{workspace.ticket.sla.breached ? 'Breached' : readable(workspace.ticket.sla.risk)}</strong></div>
                      <div className="ticket-property-readonly"><span>Case</span><strong>{workspace.case?.public_id ?? 'Not linked'}</strong></div>
                      <div className="ticket-tags">{(workspace.ticket.tags ?? []).map((tag) => <span key={tag}>{tag}</span>)}</div>
                    </> : null}
                    {detailPanel === 'activity' ? <><header><span>ACTIVITY</span><h2>Ticket history</h2></header>{timeline.map((event) => <div className="ticket-side-item" key={event.id}><strong>{readable(event.type)}</strong><span>{event.actor} · {formatRelative(event.created_at ?? workspace.ticket.updated_at)}</span><p>{event.body}</p></div>)}</> : null}
                    {detailPanel === 'links' ? <><header><span>RELATIONSHIPS</span><h2>Linked work</h2></header>{linkedTickets.length ? linkedTickets.map((ticket) => <button className="ticket-side-item link" type="button" key={ticket.id} onClick={() => openTicket(ticket.id, true)}><strong>{ticket.public_id}</strong><span>{ticket.subject}</span><small>{readable(ticket.status)}</small></button>) : <p className="ticket-empty-panel">No linked tickets.</p>}{handoffs.map((handoff) => <div className="ticket-side-item" key={handoff.id}><strong>{handoff.to_team}</strong><span>{readable(handoff.status)}</span><p>{handoff.reason}</p></div>)}</> : null}
                    {detailPanel === 'tasks' ? <><header><span>TASKS</span><h2>Child tasks</h2></header><button className="ticket-panel-action" type="button" onClick={() => setTaskDialogOpen(true)}><Plus size={15} /> Add task</button>{tasks.map((task) => <label className="ticket-task-item" key={task.id}><input type="checkbox" checked={task.complete} onChange={(event) => patchMutation.mutate({ ticket: workspace.ticket, patch: { task_item_id: task.id, task_item_complete: event.target.checked } })} /><span className={task.complete ? 'complete' : ''}>{task.label}</span></label>)}{!tasks.length ? <p className="ticket-empty-panel">No child tasks.</p> : null}</> : null}
                    {detailPanel === 'time' ? <><header><span>TIME</span><h2>Time logs</h2></header><button className="ticket-panel-action" type="button" onClick={() => setTimeDialogOpen(true)}><Plus size={15} /> Add time</button>{timeEntries.map((entry) => <div className="ticket-side-item" key={entry.id}><strong>{entry.minutes} minutes</strong><span>{entry.agent} · {formatRelative(entry.created_at)}</span><p>{entry.note || 'No note'}</p></div>)}</> : null}
                    {detailPanel === 'suggestions' ? <><header><span>OMNI AI</span><h2>Suggestions</h2></header>{knowledgeSuggestions.map((item) => <div className="ticket-side-item" key={item.article.id}><strong>{item.article.title}</strong><span>{Math.round(item.score * 100)}% match</span><p>{(item.reasons ?? []).join(' · ') || 'Related knowledge article'}</p></div>)}{macroSuggestions.map((item) => <button type="button" className="ticket-side-item link" key={item.macro.id} onClick={() => setDraft(item.macro.body)}><strong>{item.macro.name}</strong><span>Insert response</span></button>)}{!knowledgeSuggestions.length && !macroSuggestions.length ? <p className="ticket-empty-panel">No suggestions available.</p> : null}</> : null}
                  </div>
                </aside>
              </div>
            </>
          ) : null}
        </main>
      ) : (
        <main className="ticket-queue-page" aria-label="Ticket queue">
          <header className="ticket-queue-head"><div><span>TICKETS</span><h1>All tickets</h1></div><div><button type="button" className="ticket-icon-button" title="Notifications" aria-label="Notifications"><Bell size={17} /></button><button type="button" onClick={() => setNewDialogOpen(true)}><Plus size={17} /> New</button></div></header>
          <section className="ticket-view-bar" aria-label="Saved ticket views">
            <label><span>View</span><select aria-label="Saved ticket view" value={selectedViewId} onChange={(event) => { setSelectedViewId(event.target.value); setQuery(''); setStatus(''); setPriority(''); setChannel(''); setAssigneeId(''); setTeam(''); setCustomerId(''); setCreatedPeriod(''); setTag(''); setOffset(0) }}><option value="">All tickets</option>{viewsQuery.data?.map((view) => <option value={view.id} key={view.id}>{view.name}{view.owner_user_id ? '' : ' · Shared'}</option>)}</select></label>
            <button type="button" onClick={() => setSaveViewOpen(true)}><BookmarkPlus size={15} /> Save current view</button>
            {selectedViewId ? <span>{viewsQuery.data?.find((view) => view.id === selectedViewId)?.name ?? 'Saved view'}</span> : null}
          </section>
          <section className="ticket-queue-toolbar" aria-label="Ticket list controls">
            <label><input type="checkbox" checked={tickets.length > 0 && tickets.every((ticket) => selectedIds.includes(ticket.id))} onChange={() => setSelectedIds(tickets.every((ticket) => selectedIds.includes(ticket.id)) ? [] : tickets.map((ticket) => ticket.id))} aria-label="Select all tickets on page" /></label>
            <label>Sort by:<select value={sortBy} onChange={(event) => { setSortBy(event.target.value as typeof sortBy); setOffset(0) }}><option value="updated_at">Last updated</option><option value="created_at">Date created</option><option value="priority">Priority</option></select></label>
            <span />
            <div className="ticket-layout-control" aria-label="Ticket layout"><button className={layout === 'card' ? 'active' : ''} type="button" onClick={() => setLayout('card')} title="Card layout" aria-label="Card layout"><List size={16} /></button><button className={layout === 'table' ? 'active' : ''} type="button" onClick={() => setLayout('table')} title="Table layout" aria-label="Table layout"><TableProperties size={16} /></button></div>
            <button type="button" onClick={() => void downloadTicketExport()}><Download size={15} /> Export</button>
            <span className="ticket-range">{total ? `${offset + 1}-${Math.min(offset + PAGE_SIZE, total)} of ${total}` : '0 tickets'}</span>
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} aria-label="Previous page"><ArrowLeft size={15} /></button>
            <button type="button" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)} aria-label="Next page"><ArrowRight size={15} /></button>
            <button type="button" className={filtersOpen ? 'active' : ''} onClick={() => setFiltersOpen((value) => !value)} aria-expanded={filtersOpen}><Filter size={15} /> Filters{activeFilters ? ` (${activeFilters})` : ''}</button>
          </section>
          {selectedIds.length ? <section className="ticket-bulk-bar" aria-label="Bulk ticket actions"><strong>{selectedIds.length} selected</strong><label>Status<select value="" onChange={(event) => event.target.value && void bulkPatch({ status: event.target.value as Ticket['status'] })}><option value="">Choose status</option><option value="open">Open</option><option value="pending">Pending</option><option value="solved">Solved</option><option value="closed">Closed</option></select></label><label>Agent<select value="" onChange={(event) => event.target.value && void bulkPatch({ assignee_id: event.target.value })}><option value="">Choose agent</option>{users.map((user) => <option value={user.id} key={user.id}>{user.name}</option>)}</select></label><button type="button" onClick={() => setSelectedIds([])}>Clear</button></section> : null}
          <div className={`ticket-queue-layout ${filtersOpen ? '' : 'filters-closed'}`}>
            <section className={`ticket-list ${layout}`} aria-label="All tickets">
              {ticketsQuery.isLoading ? <div className="ticket-loading"><LoaderCircle className="spin" size={22} /> Loading tickets</div> : null}
              {ticketsQuery.isError ? <div className="ticket-loading error">{ticketsQuery.error.message}</div> : null}
              {!ticketsQuery.isLoading && !tickets.length ? <div className="ticket-loading"><TicketCheck size={25} /><strong>No tickets match this view</strong></div> : null}
              {tickets.map((ticket) => {
                const customer = customerById.get(ticket.customer_id)
                const checked = selectedIds.includes(ticket.id)
                return <article className={`ticket-row priority-${ticket.priority} status-${ticket.status} ${checked ? 'checked' : ''}`} key={ticket.id}>
                  <label><input type="checkbox" checked={checked} onChange={() => setSelectedIds((current) => current.includes(ticket.id) ? current.filter((id) => id !== ticket.id) : [...current, ticket.id])} aria-label={`Select ${ticket.public_id}`} /></label>
                  <button type="button" className="ticket-row-avatar" onClick={() => openTicket(ticket.id)} aria-label={`Open ${ticket.public_id}`}>{initials(customer?.name ?? ticket.subject)}</button>
                  <button type="button" className="ticket-row-main" onClick={() => openTicket(ticket.id)}><span><b>{ticket.subject}</b><strong>#{ticket.public_id.replace(/\D/g, '') || ticket.public_id}</strong></span><small>{customer?.name ?? 'Unknown customer'} · {readable(ticket.channel)} · {formatRelative(ticket.created_at)}</small><em>{ticket.sla.breached ? 'Overdue' : readable(ticket.sla.risk)}</em></button>
                  <div className="ticket-row-actions"><label className={`priority-${ticket.priority}`}><span /> <select aria-label={`Priority for ${ticket.public_id}`} value={ticket.priority} onChange={(event) => patchMutation.mutate({ ticket, patch: { priority: event.target.value as Ticket['priority'] } })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label><label><CircleUserRound size={14} /><select aria-label={`Agent for ${ticket.public_id}`} value={ticket.assignee_id ?? ''} onChange={(event) => patchMutation.mutate({ ticket, patch: { assignee_id: event.target.value || null } })}><option value="">Unassigned</option>{users.map((user) => <option value={user.id} key={user.id}>{user.name}</option>)}</select></label><select aria-label={`Status for ${ticket.public_id}`} value={ticket.status} onChange={(event) => patchMutation.mutate({ ticket, patch: { status: event.target.value as Ticket['status'] } })}><option value="open">Open</option><option value="pending">Pending</option><option value="waiting">Waiting</option><option value="solved">Solved</option><option value="closed">Closed</option></select></div>
                </article>
              })}
            </section>
            {filtersOpen ? <aside className="ticket-filter-panel" aria-label="Ticket filters"><header><strong>Filters</strong><div><button type="button" onClick={() => { setQuery(''); setSelectedViewId(''); setStatus(''); setPriority(''); setChannel(''); setAssigneeId(''); setTeam(''); setCustomerId(''); setCreatedPeriod(''); setTag(''); setOffset(0) }}>Reset</button><button className="ticket-filter-close" type="button" onClick={() => setFiltersOpen(false)} aria-label="Close filters"><X size={15} /></button></div></header><label className="ticket-filter-search"><Search size={16} /><input value={query} onChange={(event) => { setQuery(event.target.value); setOffset(0) }} placeholder="Search fields" aria-label="Search tickets" /></label><label>Agents<select value={assigneeId} onChange={(event) => { setAssigneeId(event.target.value); setOffset(0) }}><option value="">Any agent</option>{users.map((user) => <option value={user.id} key={user.id}>{user.name}</option>)}</select></label><label>Groups<select value={team} onChange={(event) => { setTeam(event.target.value); setOffset(0) }}><option value="">Any group</option>{teams.map((value) => <option value={value} key={value}>{value}</option>)}</select></label><label>Customer<select value={customerId} onChange={(event) => { setCustomerId(event.target.value); setOffset(0) }}><option value="">Any customer</option>{customersQuery.data?.map((customer) => <option value={customer.id} key={customer.id}>{customer.name}</option>)}</select></label><label>Created<select value={createdPeriod} onChange={(event) => { setCreatedPeriod(event.target.value as typeof createdPeriod); setOffset(0) }}><option value="">Any time</option><option value="today">Today</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option></select></label><label>Status<select value={status} onChange={(event) => { setStatus(event.target.value); setOffset(0) }}><option value="">Any status</option><option value="open">Open</option><option value="pending">Pending</option><option value="waiting">Waiting</option><option value="solved">Solved</option><option value="closed">Closed</option></select></label><label>Priority<select value={priority} onChange={(event) => { setPriority(event.target.value); setOffset(0) }}><option value="">Any priority</option><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label><label>Source<select value={channel} onChange={(event) => { setChannel(event.target.value); setOffset(0) }}><option value="">Any source</option><option value="email">Email</option><option value="chat">Chat</option><option value="whatsapp">WhatsApp</option><option value="facebook">Facebook</option><option value="instagram">Instagram</option><option value="portal">Portal</option><option value="internal">Internal</option></select></label><label>Tags<select value={tag} onChange={(event) => { setTag(event.target.value); setOffset(0) }}><option value="">Any tag</option>{tagsQuery.data?.filter((item) => item.active).map((item) => <option value={item.name} key={item.id}>{item.name}</option>)}</select></label></aside> : null}
          </div>
          <footer className="ticket-queue-footer"><span>{session.market.code} · {session.market.name}</span><button type="button" onClick={onSignOut}>Sign out</button></footer>
        </main>
      )}

      {notice ? <div className="ticket-toast" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Dismiss"><X size={14} /></button></div> : null}
      {saveViewOpen ? <div className="ticket-dialog-backdrop" role="presentation"><form className="ticket-dialog" onSubmit={(event) => { event.preventDefault(); saveViewMutation.mutate() }}><header><div><span>SAVED VIEW</span><h2>Save current ticket view</h2></div><button type="button" onClick={() => setSaveViewOpen(false)} aria-label="Close"><X size={18} /></button></header><label>View name<input required minLength={2} maxLength={160} value={viewName} onChange={(event) => setViewName(event.target.value)} /></label>{session.user.role === 'admin' ? <label className="ticket-checkbox-label"><input type="checkbox" checked={viewShared} onChange={(event) => setViewShared(event.target.checked)} /> Share with this market</label> : null}<footer><button type="button" onClick={() => setSaveViewOpen(false)}>Cancel</button><button type="submit" disabled={saveViewMutation.isPending}>Save view</button></footer></form></div> : null}
      {newDialogOpen ? <div className="ticket-dialog-backdrop" role="presentation"><form className="ticket-dialog" onSubmit={(event) => { event.preventDefault(); newTicketMutation.mutate() }}><header><div><span>NEW TICKET</span><h2>Create a customer ticket</h2></div><button type="button" onClick={() => setNewDialogOpen(false)} aria-label="Close"><X size={18} /></button></header><label>Customer<select required value={newCustomerId} onChange={(event) => setNewCustomerId(event.target.value)}><option value="">Select customer</option>{customersQuery.data?.map((customer) => <option value={customer.id} key={customer.id}>{customer.name} · {customer.email}</option>)}</select></label><label>Subject<input required minLength={2} maxLength={255} value={newSubject} onChange={(event) => setNewSubject(event.target.value)} /></label><label>Description<textarea required value={newDescription} onChange={(event) => setNewDescription(event.target.value)} /></label><label>Source<select value={newChannel} onChange={(event) => setNewChannel(event.target.value as Ticket['channel'])}><option value="email">Email</option><option value="chat">Chat</option><option value="whatsapp">WhatsApp</option><option value="facebook">Facebook</option><option value="instagram">Instagram</option><option value="portal">Portal</option><option value="internal">Internal</option></select></label><label>Priority<select value={newPriority} onChange={(event) => setNewPriority(event.target.value as Ticket['priority'])}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label><footer><button type="button" onClick={() => setNewDialogOpen(false)}>Cancel</button><button type="submit" disabled={newTicketMutation.isPending}>Create ticket</button></footer></form></div> : null}
      {forwardDialogOpen ? <div className="ticket-dialog-backdrop" role="presentation"><form className="ticket-dialog" onSubmit={(event) => { event.preventDefault(); forwardMutation.mutate() }}><header><div><span>FORWARD</span><h2>Forward this ticket by email</h2></div><button type="button" onClick={() => setForwardDialogOpen(false)} aria-label="Close"><X size={18} /></button></header><label>To<input type="email" required value={forwardEmail} onChange={(event) => setForwardEmail(event.target.value)} /></label><label>Subject<input required minLength={2} maxLength={255} value={forwardSubject} onChange={(event) => setForwardSubject(event.target.value)} /></label><label>Message<textarea required value={forwardBody} onChange={(event) => setForwardBody(event.target.value)} /></label><footer><button type="button" onClick={() => setForwardDialogOpen(false)}>Cancel</button><button type="submit" disabled={forwardMutation.isPending}>Queue forward</button></footer></form></div> : null}
      {taskDialogOpen ? <div className="ticket-dialog-backdrop" role="presentation"><form className="ticket-dialog" onSubmit={(event) => { event.preventDefault(); taskMutation.mutate() }}><header><div><span>CHILD TASK</span><h2>Add a task to this ticket</h2></div><button type="button" onClick={() => setTaskDialogOpen(false)} aria-label="Close"><X size={18} /></button></header><label>Task<input required maxLength={500} value={taskLabel} onChange={(event) => setTaskLabel(event.target.value)} /></label><footer><button type="button" onClick={() => setTaskDialogOpen(false)}>Cancel</button><button type="submit" disabled={taskMutation.isPending}>Add task</button></footer></form></div> : null}
      {timeDialogOpen ? <div className="ticket-dialog-backdrop" role="presentation"><form className="ticket-dialog" onSubmit={(event) => { event.preventDefault(); timeMutation.mutate() }}><header><div><span>TIME LOG</span><h2>Add time entry</h2></div><button type="button" onClick={() => setTimeDialogOpen(false)} aria-label="Close"><X size={18} /></button></header><label>Minutes<input type="number" min="1" max="1440" required value={timeMinutes} onChange={(event) => setTimeMinutes(event.target.value)} /></label><label>Note<textarea value={timeNote} onChange={(event) => setTimeNote(event.target.value)} /></label><footer><button type="button" onClick={() => setTimeDialogOpen(false)}>Cancel</button><button type="submit" disabled={timeMutation.isPending}>Add time</button></footer></form></div> : null}
      {mergeDialogOpen ? <div className="ticket-dialog-backdrop" role="presentation"><form className="ticket-dialog" onSubmit={(event) => { event.preventDefault(); mergeMutation.mutate() }}><header><div><span>MERGE</span><h2>Merge another ticket into this ticket</h2></div><button type="button" onClick={() => setMergeDialogOpen(false)} aria-label="Close"><X size={18} /></button></header><label>Source ticket<select required value={mergeSourceId} onChange={(event) => setMergeSourceId(event.target.value)}><option value="">Select ticket</option>{tickets.filter((ticket) => ticket.id !== ticketId).map((ticket) => <option value={ticket.id} key={ticket.id}>{ticket.public_id} · {ticket.subject}</option>)}</select></label><footer><button type="button" onClick={() => setMergeDialogOpen(false)}>Cancel</button><button type="submit" disabled={mergeMutation.isPending}>Merge tickets</button></footer></form></div> : null}
    </div>
  )
}

export default TicketWorkspace
