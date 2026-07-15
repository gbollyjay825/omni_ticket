import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { BackendSession } from '../../backend'
import type { Ticket, TicketWorkspace as TicketWorkspaceResponse } from './api'
import { TicketWorkspace } from './TicketWorkspace'

const api = vi.hoisted(() => ({
  createTicket: vi.fn(),
  createTicketTask: vi.fn(),
  createTicketTimeEntry: vi.fn(),
  createTicketView: vi.fn(),
  exportTickets: vi.fn(),
  fetchCustomers: vi.fn(),
  fetchScenarios: vi.fn(),
  fetchTags: vi.fn(),
  fetchTickets: vi.fn(),
  fetchTicketViews: vi.fn(),
  fetchTicketWorkspace: vi.fn(),
  fetchUsers: vi.fn(),
  forwardTicket: vi.fn(),
  mergeTickets: vi.fn(),
  runTicketScenario: vi.fn(),
  sendTicketMessage: vi.fn(),
  setTicketWatch: vi.fn(),
  updateTicket: vi.fn(),
  uploadTicketAttachment: vi.fn(),
}))

vi.mock('./api', () => api)

const now = '2026-07-14T12:00:00Z'
const ticket = {
  id: 'ticket-1',
  public_id: 'OMNI-1001',
  market_id: 'market-ng',
  case_id: 'case-1',
  customer_id: 'customer-1',
  subject: 'Date change for Lagos to London booking',
  description: 'Please move my flight to Friday.',
  channel: 'email',
  status: 'open',
  priority: 'high',
  sentiment: 'neutral',
  team: 'Customer Care',
  assignee_id: 'user-admin',
  tags: ['flight'],
  tasks: [],
  ai_summary: '',
  recommended_action: '',
  custom_fields: {},
  sla: {
    breached: false,
    risk: 'at_risk',
    first_response_due_at: now,
    resolution_due_at: now,
  },
  version: 7,
  created_at: now,
  updated_at: now,
} satisfies Ticket

const customer = {
  id: 'customer-1',
  market_id: 'market-ng',
  name: 'Leo Ahmed',
  email: 'leo@example.com',
  location: 'Lagos',
  sentiment: 'neutral',
  tags: ['flight'],
  contact_points: [],
  preferred_channels: ['email'],
}

const workspace = {
  ticket,
  customer,
  case: { id: 'case-1', public_id: 'CASE-1001' },
  timeline: [
    {
      id: 'event-1',
      ticket_id: ticket.id,
      actor: customer.name,
      body: ticket.description,
      channel: 'email',
      type: 'inbound',
      public: true,
      created_at: now,
      metadata: {},
    },
  ],
  watching: false,
  watchers: [],
  tasks: [],
  time_entries: [],
  attachments: [],
  linked_tickets: [],
  service_tasks: [],
  handoffs: [],
  suggestions: { knowledge: [], macros: [], duplicates: [] },
  previous_ticket_id: null,
  next_ticket_id: null,
  allowed_actions: ['watch', 'reply', 'private_note', 'close', 'time_log', 'attachment'],
} as unknown as TicketWorkspaceResponse

const session = {
  access_token: 'test-token',
  token_type: 'bearer',
  market: {
    id: 'market-ng',
    code: 'NG',
    name: 'Nigeria',
    timezone: 'Africa/Lagos',
    currency: 'NGN',
    default_locale: 'en-NG',
    support_email: 'support@wakanow.com',
  },
  available_markets: [],
  user: {
    id: 'user-admin',
    name: 'Gbolahan Salami',
    email: 'gbolahan@wakanow.com',
    role: 'admin',
    market_ids: ['market-ng'],
    default_market_id: 'market-ng',
    active: true,
  },
} as unknown as BackendSession

function renderWorkspace() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <TicketWorkspace
        session={session}
        online
        onNavigate={vi.fn()}
        onSignOut={vi.fn()}
      />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/?screen=inbox')
  api.fetchTickets.mockResolvedValue({ items: [ticket], total: 1 })
  api.fetchCustomers.mockResolvedValue([customer])
  api.fetchUsers.mockResolvedValue([session.user])
  api.fetchScenarios.mockResolvedValue([])
  api.fetchTags.mockResolvedValue([])
  api.fetchTicketViews.mockResolvedValue([])
  api.fetchTicketWorkspace.mockResolvedValue(workspace)
  api.updateTicket.mockResolvedValue({ ...ticket, version: ticket.version + 1 })
  api.sendTicketMessage.mockResolvedValue(workspace.timeline![0])
  api.createTicket.mockResolvedValue({ ...ticket, id: 'ticket-new', public_id: 'OMNI-1002' })
  api.createTicketTask.mockResolvedValue({
    ...ticket,
    version: ticket.version + 1,
    tasks: [{ id: 'task-1', label: 'Confirm fare', complete: false }],
  })
  api.forwardTicket.mockResolvedValue({
    ...workspace.timeline![0],
    id: 'event-forward',
    type: 'forwarded',
    public: false,
  })
  api.createTicketView.mockResolvedValue({
    id: 'view-1',
    market_id: session.market.id,
    owner_user_id: session.user.id,
    name: 'High priority this week',
    filters: { priority: 'high', created_period: '7d' },
    sort_by: 'updated_at',
    sort_order: 'desc',
    position: 100,
    shared: false,
    active: true,
    created_at: now,
    updated_at: now,
  })
})

describe('TicketWorkspace', () => {
  it('renders the API-backed queue and opens the consolidated ticket workspace', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    expect(await screen.findByRole('heading', { name: 'All tickets' })).toBeInTheDocument()
    const openButton = await screen.findByRole('button', { name: `Open ${ticket.public_id}` })
    expect(openButton).toBeInTheDocument()
    expect(screen.getAllByText(/Leo Ahmed/).length).toBeGreaterThan(0)

    await user.click(openButton)

    expect(await screen.findByRole('heading', { name: ticket.subject })).toBeInTheDocument()
    expect(api.fetchTicketWorkspace).toHaveBeenCalledWith(session, ticket.id)
    expect(screen.getByRole('complementary', { name: 'Ticket properties and apps' })).toBeInTheDocument()
  })

  it('sends inline queue changes with the current record version', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await user.selectOptions(
      await screen.findByRole('combobox', { name: `Priority for ${ticket.public_id}` }),
      'urgent',
    )

    await waitFor(() => expect(api.updateTicket).toHaveBeenCalledTimes(1))
    expect(api.updateTicket).toHaveBeenCalledWith(session, ticket.id, {
      expected_version: ticket.version,
      priority: 'urgent',
    })
  })

  it('adds a private note through the ticket reply API', async () => {
    const user = userEvent.setup()
    window.history.replaceState({}, '', `/?screen=inbox&conversation=${ticket.id}`)
    renderWorkspace()

    await user.click(await screen.findByRole('button', { name: 'Add note' }))
    await user.type(screen.getByRole('textbox', { name: 'Private note' }), 'Confirm fare difference.')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(api.sendTicketMessage).toHaveBeenCalledTimes(1))
    expect(api.sendTicketMessage).toHaveBeenCalledWith(
      session,
      ticket.id,
      expect.objectContaining({
        body: 'Confirm fare difference.',
        public: false,
      }),
    )
    expect(await screen.findByText('Private note added.')).toBeInTheDocument()
  })

  it('creates a real ticket from the queue command', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await user.click(await screen.findByRole('button', { name: 'New' }))
    const dialog = screen.getByRole('heading', { name: 'Create a customer ticket' }).closest('form')
    expect(dialog).not.toBeNull()
    await user.selectOptions(within(dialog!).getByLabelText('Customer'), customer.id)
    await user.type(within(dialog!).getByLabelText('Subject'), 'New date change request')
    await user.type(within(dialog!).getByLabelText('Description'), 'Move the booking to Monday.')
    await user.click(within(dialog!).getByRole('button', { name: 'Create ticket' }))

    await waitFor(() => expect(api.createTicket).toHaveBeenCalledTimes(1))
    expect(api.createTicket).toHaveBeenCalledWith(session, {
      customer_id: customer.id,
      subject: 'New date change request',
      description: 'Move the booking to Monday.',
      channel: 'email',
      priority: 'normal',
    })
  })

  it('forwards a ticket through the durable email command', async () => {
    const user = userEvent.setup()
    window.history.replaceState({}, '', `/?screen=inbox&conversation=${ticket.id}`)
    renderWorkspace()

    await user.click(await screen.findByRole('button', { name: 'Forward' }))
    await user.type(screen.getByLabelText('To'), 'operations@wakanow.com')
    await user.click(screen.getByRole('button', { name: 'Queue forward' }))

    await waitFor(() => expect(api.forwardTicket).toHaveBeenCalledTimes(1))
    expect(api.forwardTicket).toHaveBeenCalledWith(
      session,
      ticket.id,
      expect.objectContaining({
        expected_version: ticket.version,
        to_email: 'operations@wakanow.com',
        subject: `Fwd: ${ticket.subject}`,
      }),
    )
  })

  it('creates a persisted child task from ticket detail', async () => {
    const user = userEvent.setup()
    window.history.replaceState({}, '', `/?screen=inbox&conversation=${ticket.id}`)
    renderWorkspace()

    await user.click(await screen.findByRole('button', { name: 'Child task' }))
    await user.type(screen.getByLabelText('Task'), 'Confirm fare difference')
    await user.click(screen.getByRole('button', { name: 'Add task' }))

    await waitFor(() => expect(api.createTicketTask).toHaveBeenCalledTimes(1))
    expect(api.createTicketTask).toHaveBeenCalledWith(session, ticket.id, {
      expected_version: ticket.version,
      label: 'Confirm fare difference',
    })
  })

  it('persists the active queue filters as a saved view', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await user.selectOptions(await screen.findByLabelText('Priority'), 'high')
    await user.selectOptions(screen.getByLabelText('Created'), '7d')
    await user.click(screen.getByRole('button', { name: 'Save current view' }))
    await user.type(screen.getByLabelText('View name'), 'High priority this week')
    await user.click(screen.getByRole('button', { name: 'Save view' }))

    await waitFor(() => expect(api.createTicketView).toHaveBeenCalledTimes(1))
    expect(api.createTicketView).toHaveBeenCalledWith(session, {
      name: 'High priority this week',
      filters: {
        priority: 'high',
        created_period: '7d',
      },
      sort_by: 'updated_at',
      sort_order: 'desc',
      position: 100,
      shared: false,
    })
    expect(await screen.findByText('Saved view “High priority this week” created.')).toBeInTheDocument()
  })
})
