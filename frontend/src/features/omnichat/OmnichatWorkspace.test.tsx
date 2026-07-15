import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { BackendSession } from '../../backend'
import type {
  Conversation,
  ConversationAttachment,
  ConversationContext,
  ConversationMessage,
} from './api'
import { OmnichatWorkspace } from './OmnichatWorkspace'

const api = vi.hoisted(() => ({
  assignConversation: vi.fn(),
  changeConversationStatus: vi.fn(),
  conversationAttachmentDownloadUrl: vi.fn(
    (conversationId: string, attachmentId: string) =>
      `/api/v1/conversations/${conversationId}/attachments/${attachmentId}/download`,
  ),
  createConversation: vi.fn(),
  createConversationMessage: vi.fn(),
  fetchConversation: vi.fn(),
  fetchConversationContext: vi.fn(),
  fetchConversationMessages: vi.fn(),
  fetchConversations: vi.fn(),
  fetchConversationTopics: vi.fn(),
  fetchConversationViews: vi.fn(),
  fetchCustomers: vi.fn(),
  fetchCustomerTickets: vi.fn(),
  fetchFeatureCapabilities: vi.fn(),
  fetchResponseMacros: vi.fn(),
  fetchSupportGroups: vi.fn(),
  fetchUsers: vi.fn(),
  linkConversationTicket: vi.fn(),
  intelliAssignConversation: vi.fn(),
  markConversationMessageRead: vi.fn(),
  updateConversation: vi.fn(),
  uploadConversationAttachment: vi.fn(),
}))

const realtime = vi.hoisted(() => ({
  markRead: vi.fn(),
  sendTyping: vi.fn(),
}))

vi.mock('./api', () => api)
vi.mock('./useOmnichatRealtime', () => ({
  useOmnichatRealtime: () => ({
    connectionStatus: 'connected',
    markRead: realtime.markRead,
    sendTyping: realtime.sendTyping,
    typingByConversation: {},
  }),
}))

const now = '2026-07-14T12:00:00Z'
const conversation = {
  id: 'conversation-1',
  market_id: 'market-ng',
  public_id: 'CHAT-1001',
  case_id: 'case-1',
  customer_id: 'customer-1',
  customer_name: 'Leo Ahmed',
  customer_email: 'leo@example.com',
  assignee_name: '',
  group_name: '',
  topic_name: '',
  channel: 'whatsapp',
  status: 'open',
  priority: 'high',
  version: 3,
  subject: 'Date change for Lagos to London booking',
  latest_message: 'Please move my flight to Friday.',
  unread_count: 1,
  last_message_at: now,
  created_at: now,
  updated_at: now,
  metadata: {},
} satisfies Conversation

const message = {
  id: 'message-1',
  market_id: 'market-ng',
  conversation_id: conversation.id,
  sender_type: 'customer',
  sender_name: 'Leo Ahmed',
  visibility: 'public',
  body: 'Please move my flight to Friday.',
  delivery_state: 'received',
  version: 1,
  sent_at: now,
  created_at: now,
  updated_at: now,
  content: {},
  metadata: {},
} satisfies ConversationMessage

const attachment = {
  id: 'attachment-1',
  market_id: 'market-ng',
  conversation_id: conversation.id,
  message_id: null,
  filename: 'itinerary.pdf',
  content_type: 'application/pdf',
  size_bytes: 2048,
  storage_provider: 'local',
  scan_status: 'clean',
  scan_result: 'clean',
  lifecycle_status: 'active',
  retained_until: '2026-08-14T12:00:00Z',
  deleted_at: null,
  deleted_by: null,
  deletion_reason: null,
  purged_at: null,
  uploaded_by: 'user-admin',
  created_at: now,
  updated_at: now,
} satisfies ConversationAttachment

const context = {
  conversation,
  customer: {
    id: 'customer-1',
    name: 'Leo Ahmed',
    email: 'leo@example.com',
    market_id: 'market-ng',
    location: 'Lagos',
    sentiment: 'neutral',
    tags: ['flight'],
    contact_points: [],
    preferred_channels: ['whatsapp'],
  },
  case: { id: 'case-1', public_id: 'CASE-1001', ticket_count: 0 },
  participants: [],
  assignments: [],
  linked_tickets: [],
  attachments: [],
  customer_history: [],
  allowed_actions: ['reply', 'private_note', 'resolve'],
} as unknown as ConversationContext

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
  available_markets: [
    {
      id: 'market-ng',
      code: 'NG',
      name: 'Nigeria',
      timezone: 'Africa/Lagos',
      currency: 'NGN',
      default_locale: 'en-NG',
      support_email: 'support@wakanow.com',
    },
  ],
  user: {
    id: 'user-admin',
    name: 'Gbolahan Salami',
    email: 'gbolahan@wakanow.com',
    role: 'admin',
    market_ids: ['market-ng'],
    default_market_id: 'market-ng',
    active: true,
    password_reset_required: false,
    mfa_enabled: true,
    permission_profile: 'role_default',
    permission_overrides: { allow: [], deny: [] },
    effective_permissions: [],
  },
} as unknown as BackendSession

function renderWorkspace(activeSession: BackendSession = session) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <OmnichatWorkspace
        session={activeSession}
        online
        onNavigate={vi.fn()}
        onSwitchMarket={vi.fn()}
        onSignOut={vi.fn()}
      />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  window.history.replaceState({}, '', '/?screen=channels')
  vi.clearAllMocks()
  api.fetchFeatureCapabilities.mockResolvedValue([
    { key: 'omnichat_parity', available: true, enabled: true, reason: 'Pilot enabled', configuration: {} },
  ])
  api.fetchConversationViews.mockResolvedValue([])
  api.fetchConversationTopics.mockResolvedValue([])
  api.fetchUsers.mockResolvedValue([session.user])
  api.fetchSupportGroups.mockResolvedValue([])
  api.fetchResponseMacros.mockResolvedValue([])
  api.fetchCustomers.mockResolvedValue([context.customer])
  api.fetchConversations.mockResolvedValue({ items: [conversation], next_cursor: null })
  api.fetchConversation.mockResolvedValue(conversation)
  api.fetchConversationMessages.mockResolvedValue({ items: [message], next_cursor: null })
  api.fetchConversationContext.mockResolvedValue(context)
  api.fetchCustomerTickets.mockResolvedValue([])
  api.markConversationMessageRead.mockResolvedValue({})
  api.uploadConversationAttachment.mockResolvedValue(attachment)
  api.createConversationMessage.mockResolvedValue({
    ...message,
    id: 'message-private',
    sender_type: 'agent',
    sender_name: session.user.name,
    visibility: 'private',
    body: 'Check fare difference before replying.',
    delivery_state: 'internal',
  })
  api.changeConversationStatus.mockResolvedValue({ ...conversation, status: 'resolved', version: 4 })
  api.intelliAssignConversation.mockResolvedValue({
    ...conversation,
    assignee_id: session.user.id,
    assignee_name: session.user.name,
    version: 4,
  })
})

describe('OmnichatWorkspace', () => {
  it('renders the Freshchat-style queue, thread, and customer context from APIs', async () => {
    renderWorkspace()

    expect(await screen.findByRole('heading', { name: 'Team Inbox' })).toBeInTheDocument()
    expect(screen.getAllByText('Leo Ahmed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Date change for Lagos to London booking').length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'Customer details' })).toBeInTheDocument()
    expect(screen.getAllByText('Please move my flight to Friday.').length).toBeGreaterThan(0)
    expect(await screen.findByRole('button', { name: 'Attach a file' })).toBeEnabled()
  })

  it('uploads a clean attachment and sends it through the conversation message contract', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    const file = new File(['ticket document'], 'itinerary.pdf', { type: 'application/pdf' })
    await user.upload(await screen.findByLabelText('Choose conversation attachment'), file)

    await waitFor(() => expect(api.uploadConversationAttachment).toHaveBeenCalledWith(
      session,
      conversation.id,
      file,
    ))
    expect(await screen.findByText('itinerary.pdf is ready to send.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove itinerary.pdf' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(api.createConversationMessage).toHaveBeenCalledTimes(1))
    expect(api.createConversationMessage).toHaveBeenCalledWith(
      session,
      conversation.id,
      expect.objectContaining({
        body: '',
        content: { attachment_ids: [attachment.id] },
        expected_version: conversation.version,
      }),
    )
  })

  it('reports a customer-context API failure and retries the real query', async () => {
    const user = userEvent.setup()
    api.fetchConversationContext.mockRejectedValueOnce(new Error('Context request failed.'))
    renderWorkspace()

    expect(await screen.findByText('Customer context is unavailable')).toBeInTheDocument()
    expect(screen.getByText('Context request failed.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => expect(api.fetchConversationContext).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Conversation properties')).toBeInTheDocument()
  })

  it('sends a private note with the current record version', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await user.click(await screen.findByRole('button', { name: 'Private note' }))
    await user.type(screen.getByRole('textbox', { name: 'Private note' }), 'Check fare difference before replying.')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(api.createConversationMessage).toHaveBeenCalledTimes(1))
    expect(api.createConversationMessage).toHaveBeenCalledWith(
      session,
      conversation.id,
      expect.objectContaining({
        body: 'Check fare difference before replying.',
        visibility: 'private',
        expected_version: 3,
      }),
    )
    expect(await screen.findByText('Private note added.')).toBeInTheDocument()
  })

  it('resolves the active conversation through the version-aware API', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await user.click(await screen.findByRole('button', { name: 'Resolve' }))

    await waitFor(() => expect(api.changeConversationStatus).toHaveBeenCalledTimes(1))
    expect(api.changeConversationStatus).toHaveBeenCalledWith(
      session,
      conversation.id,
      'resolve',
      expect.objectContaining({ expected_version: 3 }),
    )
  })

  it('supports Freshchat-compatible resolve and IntelliAssign shortcuts', async () => {
    renderWorkspace()
    await screen.findByRole('button', { name: 'Resolve' })

    fireEvent.keyDown(window, { key: 'y', ctrlKey: true })
    await waitFor(() => expect(api.changeConversationStatus).toHaveBeenCalledTimes(1))

    fireEvent.keyDown(window, { key: 'i', altKey: true, shiftKey: true })
    await waitFor(() => expect(api.intelliAssignConversation).toHaveBeenCalledTimes(1))
    expect(api.intelliAssignConversation).toHaveBeenCalledWith(session, conversation.id, {
      expected_version: conversation.version,
      reason: 'IntelliAssign from Omnichat workspace',
    })
  })

  it('opens the complete shortcut reference from Team Inbox', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await user.click(await screen.findByRole('button', { name: 'Keyboard shortcuts' }))

    expect(screen.getByRole('dialog', { name: 'Keyboard shortcuts' })).toBeInTheDocument()
    expect(screen.getByText('Send and resolve')).toBeInTheDocument()
    expect(screen.getByText('IntelliAssign')).toBeInTheDocument()
  })

  it('keeps non-pilot agents out of the workspace', async () => {
    api.fetchFeatureCapabilities.mockResolvedValue([
      { key: 'omnichat_parity', available: false, enabled: false, reason: 'Not assigned', configuration: {} },
    ])
    renderWorkspace({
      ...session,
      user: { ...session.user, id: 'user-agent', role: 'agent' },
    })

    expect(await screen.findByRole('heading', { name: 'Omnichat pilot is not enabled' })).toBeInTheDocument()
  })
})
