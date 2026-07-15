import { getBackendBaseUrl, type BackendSession } from '../../backend'
import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'

export type Conversation = components['schemas']['Conversation']
export type ConversationAttachment = components['schemas']['ConversationAttachment']
export type ConversationContext = components['schemas']['ConversationContext']
export type ConversationMessage = components['schemas']['ConversationMessage']
export type ConversationPage = components['schemas']['ConversationPage']
export type ConversationTopic = components['schemas']['ConversationTopic']
export type ConversationView = components['schemas']['ConversationView']
export type Customer = components['schemas']['Customer']
export type FeatureCapability = components['schemas']['FeatureCapability']
export type ResponseMacro = components['schemas']['ResponseMacro']
export type SupportGroup = components['schemas']['SupportGroup']
export type Ticket = components['schemas']['Ticket']
export type User = components['schemas']['User']

function apiError(error: unknown): Error {
  if (typeof error === 'object' && error && 'detail' in error) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === 'string') return new Error(detail)
    if (typeof detail === 'object' && detail && 'message' in detail) {
      const message = (detail as { message?: unknown }).message
      if (typeof message === 'string') return new Error(message)
    }
  }
  return new Error('The Omnichat request could not be completed.')
}

export interface ConversationFilters {
  cursor?: string
  limit?: number
  viewId?: string
  status?: string
  channel?: components['schemas']['ChannelType']
  assigneeId?: string
  groupId?: string
  topicId?: string
  query?: string
}

export async function fetchConversations(
  session: BackendSession,
  filters: ConversationFilters,
): Promise<ConversationPage> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/conversations', {
    params: {
      query: {
        cursor: filters.cursor,
        limit: filters.limit ?? 30,
        view_id: filters.viewId,
        status: filters.status,
        channel: filters.channel,
        assignee_id: filters.assigneeId,
        group_id: filters.groupId,
        topic_id: filters.topicId,
        q: filters.query,
      },
    },
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchConversation(
  session: BackendSession,
  conversationId: string,
): Promise<Conversation> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/conversations/{conversation_id}', {
    params: { path: { conversation_id: conversationId } },
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchConversationContext(
  session: BackendSession,
  conversationId: string,
): Promise<ConversationContext> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/conversations/{conversation_id}/context', {
    params: { path: { conversation_id: conversationId } },
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchConversationMessages(
  session: BackendSession,
  conversationId: string,
) {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/conversations/{conversation_id}/messages', {
    params: {
      path: { conversation_id: conversationId },
      query: { limit: 100 },
    },
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function createConversationMessage(
  session: BackendSession,
  conversationId: string,
  payload: components['schemas']['CreateConversationMessageRequest'],
): Promise<ConversationMessage> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/conversations/{conversation_id}/messages', {
    params: { path: { conversation_id: conversationId } },
    body: payload,
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function uploadConversationAttachment(
  session: BackendSession,
  conversationId: string,
  file: File,
): Promise<ConversationAttachment> {
  const params = new URLSearchParams({ filename: file.name })
  const headers = new Headers({
    'Content-Type': file.type || 'application/octet-stream',
    'X-Omni-Market': session.market.id,
  })
  if (session.access_token) headers.set('Authorization', `Bearer ${session.access_token}`)
  const response = await fetch(
    `${getBackendBaseUrl()}/conversations/${encodeURIComponent(conversationId)}/attachments/binary?${params}`,
    {
      method: 'POST',
      headers,
      credentials: 'include',
      body: file,
    },
  )
  if (!response.ok) {
    let error: unknown
    try {
      error = await response.json()
    } catch {
      error = undefined
    }
    throw apiError(error)
  }
  return response.json() as Promise<ConversationAttachment>
}

export function conversationAttachmentDownloadUrl(
  conversationId: string,
  attachmentId: string,
) {
  return (
    `${getBackendBaseUrl()}/conversations/${encodeURIComponent(conversationId)}`
    + `/attachments/${encodeURIComponent(attachmentId)}/download`
  )
}

export async function assignConversation(
  session: BackendSession,
  conversationId: string,
  payload: components['schemas']['AssignConversationRequest'],
): Promise<Conversation> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/conversations/{conversation_id}/assignment', {
    params: { path: { conversation_id: conversationId } },
    body: payload,
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function intelliAssignConversation(
  session: BackendSession,
  conversationId: string,
  payload: components['schemas']['IntelliAssignConversationRequest'],
): Promise<Conversation> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST(
    '/api/v1/conversations/{conversation_id}/intelli-assign',
    {
      params: { path: { conversation_id: conversationId } },
      body: payload,
    },
  )
  if (error || !data) throw apiError(error)
  return data
}

export async function changeConversationStatus(
  session: BackendSession,
  conversationId: string,
  action: 'resolve' | 'reopen',
  payload: components['schemas']['ChangeConversationStatusRequest'],
): Promise<Conversation> {
  const client = createOmniApiClient(session)
  const path =
    action === 'resolve'
      ? '/api/v1/conversations/{conversation_id}/resolve'
      : '/api/v1/conversations/{conversation_id}/reopen'
  const request =
    path === '/api/v1/conversations/{conversation_id}/resolve'
      ? client.POST('/api/v1/conversations/{conversation_id}/resolve', {
          params: { path: { conversation_id: conversationId } },
          body: payload,
        })
      : client.POST('/api/v1/conversations/{conversation_id}/reopen', {
          params: { path: { conversation_id: conversationId } },
          body: payload,
        })
  const { data, error } = await request
  if (error || !data) throw apiError(error)
  return data
}

export async function updateConversation(
  session: BackendSession,
  conversationId: string,
  payload: components['schemas']['UpdateConversationRequest'],
): Promise<Conversation> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.PATCH('/api/v1/conversations/{conversation_id}', {
    params: { path: { conversation_id: conversationId } },
    body: payload,
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function markConversationMessageRead(
  session: BackendSession,
  conversationId: string,
  messageId: string,
) {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/conversations/{conversation_id}/receipts', {
    params: { path: { conversation_id: conversationId } },
    body: { message_id: messageId, receipt_type: 'read' },
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function linkConversationTicket(
  session: BackendSession,
  conversationId: string,
  ticketId: string,
) {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST(
    '/api/v1/conversations/{conversation_id}/linked-tickets',
    {
      params: { path: { conversation_id: conversationId } },
      body: { ticket_id: ticketId, relationship: 'linked' },
    },
  )
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchConversationViews(session: BackendSession): Promise<ConversationView[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/conversation-views')
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchConversationTopics(
  session: BackendSession,
): Promise<ConversationTopic[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/conversation-topics')
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchFeatureCapabilities(
  session: BackendSession,
): Promise<FeatureCapability[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/features')
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchUsers(session: BackendSession): Promise<User[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/auth/users')
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchSupportGroups(session: BackendSession): Promise<SupportGroup[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/support-groups')
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchResponseMacros(session: BackendSession): Promise<ResponseMacro[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/macros')
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchCustomerTickets(
  session: BackendSession,
  customerId: string,
): Promise<Ticket[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/tickets', {
    params: { query: { customer_id: customerId, limit: 100 } },
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchCustomers(session: BackendSession): Promise<Customer[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/customers', {
    params: { query: { limit: 100, offset: 0 } },
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function createConversation(
  session: BackendSession,
  payload: components['schemas']['CreateConversationRequest'],
): Promise<Conversation> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/conversations', { body: payload })
  if (error || !data) throw apiError(error)
  return data
}
