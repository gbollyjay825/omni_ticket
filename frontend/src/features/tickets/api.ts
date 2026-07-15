import type { BackendSession } from '../../backend'
import { exportBackendReport, uploadBackendAttachment } from '../../backend'
import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'

export type Ticket = components['schemas']['Ticket']
export type TicketWorkspace = components['schemas']['TicketWorkspace']
export type Customer = components['schemas']['Customer']
export type User = components['schemas']['User']
export type ScenarioAutomation = components['schemas']['ScenarioAutomation']
export type TicketView = components['schemas']['TicketView']
export type Tag = components['schemas']['Tag']
export type TimelineEvent = components['schemas']['TimelineEvent']
export type TicketUpdate = components['schemas']['UpdateTicketRequest']
export type CreateTicketInput = components['schemas']['CreateTicketRequest']

function apiError(error: unknown): Error {
  if (typeof error === 'object' && error && 'detail' in error) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === 'string') return new Error(detail)
    if (typeof detail === 'object' && detail && 'message' in detail) {
      const message = (detail as { message?: unknown }).message
      if (typeof message === 'string') return new Error(message)
    }
  }
  return new Error('The ticket request could not be completed.')
}

export interface TicketFilters {
  viewId?: string
  query?: string
  status?: string
  channel?: Ticket['channel']
  priority?: Ticket['priority']
  assigneeId?: string
  team?: string
  customerId?: string
  createdPeriod?: 'today' | '7d' | '30d'
  tag?: string
  sortBy?: 'updated_at' | 'created_at' | 'public_id' | 'subject' | 'status' | 'priority' | 'channel'
  sortOrder?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export async function fetchTickets(session: BackendSession, filters: TicketFilters) {
  const client = createOmniApiClient(session)
  const { data, error, response } = await client.GET('/api/v1/tickets', {
    params: {
      query: {
        view_id: filters.viewId,
        q: filters.query,
        status: filters.status,
        channel: filters.channel,
        priority: filters.priority,
        assignee_id: filters.assigneeId,
        team: filters.team,
        customer_id: filters.customerId,
        created_period: filters.createdPeriod,
        tag: filters.tag,
        sort_by: filters.sortBy ?? 'updated_at',
        sort_order: filters.sortOrder ?? 'desc',
        limit: filters.limit ?? 30,
        offset: filters.offset ?? 0,
      },
    },
  })
  if (error || !data) throw apiError(error)
  return {
    items: data,
    total: Number(response.headers.get('x-total-count') ?? data.length),
  }
}

export async function fetchTicketViews(session: BackendSession): Promise<TicketView[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/ticket-views')
  if (error || !data) throw apiError(error)
  return data
}

export async function createTicketView(
  session: BackendSession,
  payload: components['schemas']['CreateTicketViewRequest'],
): Promise<TicketView> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/ticket-views', { body: payload })
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchTags(session: BackendSession): Promise<Tag[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/tags')
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchTicketWorkspace(
  session: BackendSession,
  ticketId: string,
): Promise<TicketWorkspace> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/tickets/{ticket_id}/workspace', {
    params: { path: { ticket_id: ticketId } },
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function updateTicket(
  session: BackendSession,
  ticketId: string,
  patch: components['schemas']['UpdateTicketRequest'],
): Promise<Ticket> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.PATCH('/api/v1/tickets/{ticket_id}', {
    params: { path: { ticket_id: ticketId } },
    body: patch,
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function sendTicketMessage(
  session: BackendSession,
  ticketId: string,
  payload: components['schemas']['ReplyRequest'],
): Promise<TimelineEvent> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/tickets/{ticket_id}/reply', {
    params: { path: { ticket_id: ticketId } },
    body: payload,
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function forwardTicket(
  session: BackendSession,
  ticketId: string,
  payload: components['schemas']['ForwardTicketRequest'],
): Promise<TimelineEvent> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/tickets/{ticket_id}/forward', {
    params: { path: { ticket_id: ticketId } },
    body: payload,
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function createTicketTask(
  session: BackendSession,
  ticketId: string,
  payload: components['schemas']['CreateTicketTaskRequest'],
): Promise<Ticket> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/tickets/{ticket_id}/tasks', {
    params: { path: { ticket_id: ticketId } },
    body: payload,
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function createTicket(
  session: BackendSession,
  payload: CreateTicketInput,
): Promise<Ticket> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/tickets', { body: payload })
  if (error || !data) throw apiError(error)
  return data
}

export function exportTickets(session: BackendSession) {
  return exportBackendReport('tickets', session)
}

export async function setTicketWatch(
  session: BackendSession,
  ticketId: string,
  watching: boolean,
) {
  const client = createOmniApiClient(session)
  const request = watching
    ? client.PUT('/api/v1/tickets/{ticket_id}/watch', {
        params: { path: { ticket_id: ticketId } },
      })
    : client.DELETE('/api/v1/tickets/{ticket_id}/watch', {
        params: { path: { ticket_id: ticketId } },
      })
  const { error } = await request
  if (error) throw apiError(error)
  return true
}

export async function createTicketTimeEntry(
  session: BackendSession,
  ticketId: string,
  payload: components['schemas']['CreateTicketTimeEntryRequest'],
) {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/tickets/{ticket_id}/time-entries', {
    params: { path: { ticket_id: ticketId } },
    body: payload,
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchCustomers(session: BackendSession): Promise<Customer[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/customers', {
    params: { query: { limit: 500, offset: 0 } },
  })
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchUsers(session: BackendSession): Promise<User[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/auth/users')
  if (error || !data) throw apiError(error)
  return data
}

export async function fetchScenarios(session: BackendSession): Promise<ScenarioAutomation[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/scenario-automations')
  if (error || !data) throw apiError(error)
  return data
}

export async function runTicketScenario(
  session: BackendSession,
  ticketId: string,
  scenarioId: string,
): Promise<Ticket> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST(
    '/api/v1/tickets/{ticket_id}/scenarios/{scenario_id}/run',
    { params: { path: { ticket_id: ticketId, scenario_id: scenarioId } } },
  )
  if (error || !data) throw apiError(error)
  return data
}

export async function mergeTickets(
  session: BackendSession,
  targetTicketId: string,
  sourceTicketId: string,
) {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/tickets/{ticket_id}/merge', {
    params: { path: { ticket_id: targetTicketId } },
    body: {
      source_ticket_id: sourceTicketId,
      reason: 'Merged from the Omni ticket workspace',
      close_source: true,
      actor: session.user.name,
    },
  })
  if (error || !data) throw apiError(error)
  return data
}

export function uploadTicketAttachment(
  session: BackendSession,
  ticketId: string,
  file: File,
) {
  return uploadBackendAttachment(ticketId, file, session)
}
