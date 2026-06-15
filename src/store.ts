import { useEffect, useMemo, useState } from 'react'
import { openDB, type DBSchema } from 'idb'
import type {
  AgentProfile,
  CaseRecord,
  Channel,
  ChannelId,
  ComposerInput,
  ConversationStatus,
  CustomerProfile,
  DuplicateTicketSuggestion,
  HandoffStatus,
  InboxFilters,
  KnowledgeArticle,
  NewTicketInput,
  OmniConversation,
  OmniState,
  Priority,
  ResponseMacro,
  ResponseMacroSuggestion,
  RuleStatus,
  ScreenId,
  Sentiment,
  SlaPolicy,
  BusinessHours,
  TicketTemplate,
  Tag,
  CsatSurvey,
  EmailNotification,
  ScenarioAutomation,
  CustomFieldDefinition,
  CustomObject,
  DiscussionTopic,
  Product,
  SavedReport,
  ServiceAppointment,
  SlaState,
  SupportGroup,
  TicketField,
  TimelineEvent,
  TimelineType,
  WorkspaceSettings,
} from './domain'
import {
  type BackendAgent,
  changeBackendPassword,
  completeOidcLoginBackend,
  confirmBackendMfa,
  createBackendAttachment,
  createBackendSlaPolicy,
  createBackendBusinessHours,
  createBackendTicketTemplate,
  createBackendTag,
  createBackendCsatSurvey,
  createBackendEmailNotification,
  createBackendScenarioAutomation,
  createBackendCustomFieldDefinition,
  createBackendCustomObject,
  createBackendProduct,
  createBackendSavedReport,
  createBackendServiceAppointment,
  createBackendDiscussionTopic,
  patchBackendDiscussionTopic,
  createBackendSupportGroup,
  createBackendTicketField,
  createBackendUser,
  attachBackendCaseTicket,
  createBackendCase,
  createBackendHandoff,
  detachBackendCaseTicket,
  updateBackendCase,
  createBackendTicket,
  disableBackendMfa,
  enrollBackendMfa,
  type BackendAutomationRule,
  type BackendChannel,
  type BackendCompany,
  type BackendCreateSlaPolicyInput,
  type BackendCreateBusinessHoursInput,
  type BackendCreateTicketTemplateInput,
  type BackendCreateTagInput,
  type BackendCreateCsatSurveyInput,
  type BackendCreateEmailNotificationInput,
  type BackendCreateScenarioAutomationInput,
  type BackendCreateCustomFieldDefinitionInput,
  type BackendCreateCustomObjectInput,
  type BackendCreateProductInput,
  type BackendCreateSavedReportInput,
  type BackendCreateServiceAppointmentInput,
  type BackendCreateSupportGroupInput,
  type BackendCreateUserInput,
  type BackendCustomer,
  type BackendDuplicateTicketSuggestion,
  type BackendCase,
  type BackendHandoff,
  type BackendKnowledgeArticle,
  type BackendCreateKnowledgeInput,
  type BackendUpdateKnowledgeInput,
  createBackendKnowledgeArticle,
  type BackendCreateCustomerInput,
  type BackendUpdateCustomerInput,
  createBackendCustomer,
  patchBackendCustomer,
  type BackendCreateTicketFieldInput,
  fetchBackendSnapshot,
  fetchOidcProviderConfig,
  getBackendBaseUrl,
  loginBackend,
  patchBackendAutomationRule,
  patchBackendChannel,
  patchBackendHandoff,
  patchBackendKnowledgeArticle,
  patchBackendOperationalAlert,
  patchBackendSettings,
  patchBackendSlaPolicy,
  patchBackendBusinessHours,
  patchBackendTicketTemplate,
  patchBackendTag,
  patchBackendCsatSurvey,
  patchBackendEmailNotification,
  patchBackendScenarioAutomation,
  patchBackendCustomFieldDefinition,
  patchBackendCustomObject,
  patchBackendProduct,
  patchBackendSavedReport,
  patchBackendServiceAppointment,
  patchBackendSupportGroup,
  patchBackendTicket,
  patchBackendTicketField,
  patchBackendUser,
  type BackendLoginInput,
  type BackendMfaEnrollment,
  type BackendOidcCallbackInput,
  type BackendOperationalAlertStatus,
  type BackendResponseMacro,
  type BackendCreateResponseMacroInput,
  type BackendUpdateResponseMacroInput,
  type BackendResponseMacroSuggestion,
  type BackendSession,
  type BackendSlaPolicy,
  type BackendBusinessHours,
  type BackendTicketTemplate,
  type BackendTag,
  type BackendCsatSurvey,
  type BackendEmailNotification,
  type BackendScenarioAutomation,
  type BackendCustomFieldDefinition,
  type BackendCustomObject,
  type BackendProduct,
  type BackendSavedReport,
  type BackendServiceAppointment,
  type BackendDiscussionTopic,
  type BackendCreateDiscussionTopicInput,
  type BackendUpdateDiscussionTopicInput,
  type BackendSyncState,
  type BackendUpdateSlaPolicyInput,
  type BackendUpdateBusinessHoursInput,
  type BackendUpdateTicketTemplateInput,
  type BackendUpdateTagInput,
  type BackendUpdateCsatSurveyInput,
  type BackendUpdateEmailNotificationInput,
  type BackendUpdateScenarioAutomationInput,
  type BackendUpdateCustomFieldDefinitionInput,
  type BackendUpdateCustomObjectInput,
  type BackendUpdateProductInput,
  type BackendUpdateSavedReportInput,
  type BackendUpdateServiceAppointmentInput,
  type BackendUpdateSupportGroupInput,
  type BackendUpdateUserInput,
  type BackendUpdateTicketFieldInput,
  type BackendTicket,
  type BackendTicketField,
  type BackendTicketContext,
  type BackendTimelineEvent,
  type BackendSnapshot,
  postBackendReply,
  recordBackendResponseMacroUse,
  createBackendResponseMacro,
  patchBackendResponseMacro,
  retryBackendOutboundMessage,
  startOidcLoginBackend,
  uploadBackendAttachment,
} from './backend'
import { initialOmniState } from './seed'

interface TicketDeskDb extends DBSchema {
  state: {
    key: string
    value: OmniState
  }
}

const dbName = 'omni-ticket'
const stateKey = 'state-v20'
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
  'portal',
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

function sessionFromSnapshot(session: BackendSession, snapshot: BackendSnapshot): BackendSession {
  return {
    ...session,
    user: snapshot.session.user,
    market: snapshot.session.market,
  }
}

function sessionChanged(current: BackendSession, next: BackendSession) {
  return (
    current.market.id !== next.market.id ||
    JSON.stringify(current.user) !== JSON.stringify(next.user)
  )
}

function isBackendAuthError(error: unknown) {
  if (!(error instanceof Error)) return false
  return (
    error.message.startsWith('401') ||
    error.message === 'Session expired' ||
    error.message === 'Invalid session' ||
    error.message === 'Authentication required'
  )
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
    ticketFields: state.ticketFields ?? initialOmniState.ticketFields,
    supportGroups: state.supportGroups ?? initialOmniState.supportGroups,
    slaPolicies: state.slaPolicies ?? initialOmniState.slaPolicies,
    businessHours: state.businessHours ?? initialOmniState.businessHours,
    ticketTemplates: state.ticketTemplates ?? initialOmniState.ticketTemplates,
    tags: state.tags ?? initialOmniState.tags,
    csatSurveys: state.csatSurveys ?? initialOmniState.csatSurveys,
    emailNotifications: state.emailNotifications ?? initialOmniState.emailNotifications,
    scenarioAutomations: state.scenarioAutomations ?? initialOmniState.scenarioAutomations,
    customFieldDefinitions: state.customFieldDefinitions ?? initialOmniState.customFieldDefinitions,
    customObjects: state.customObjects ?? initialOmniState.customObjects,
    products: state.products ?? initialOmniState.products,
    savedReports: state.savedReports ?? initialOmniState.savedReports,
    serviceAppointments: state.serviceAppointments ?? initialOmniState.serviceAppointments,
    discussionTopics: state.discussionTopics ?? initialOmniState.discussionTopics,
    cases: state.cases ?? initialOmniState.cases,
    responseMacros: state.responseMacros ?? initialOmniState.responseMacros,
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
  if (event.type === 'attachment_added') return 'automation'
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

function mapTicketField(field: BackendTicketField): TicketField {
  return {
    id: field.id,
    key: field.key,
    label: field.label,
    fieldType: field.field_type,
    required: field.required,
    active: field.active,
    system: field.system,
    options: field.options,
    channels: field.channels.map(normalizeChannelId),
    placeholder: field.placeholder,
    helpText: field.help_text,
    position: field.position,
    updatedAt: field.updated_at,
  }
}

function mapSupportGroup(group: BackendSnapshot['supportGroups'][number]): SupportGroup {
  return {
    id: group.id,
    name: group.name,
    description: group.description,
    teamEmail: group.team_email,
    active: group.active,
    channels: group.channels.map(normalizeChannelId),
    skills: group.skills,
    memberCount: group.member_count,
    openTicketCount: group.open_ticket_count,
    slaRiskCount: group.sla_risk_count,
    updatedAt: group.updated_at,
  }
}

function mapSlaPolicy(policy: BackendSlaPolicy): SlaPolicy {
  return {
    id: policy.id,
    name: policy.name,
    active: policy.active,
    channels: policy.channels.map(normalizeChannelId),
    priority: mapPriority(policy.priority),
    firstResponseMinutes: policy.first_response_minutes,
    resolutionMinutes: policy.resolution_minutes,
    businessHours: policy.business_hours,
    position: policy.position,
    updatedAt: policy.updated_at,
  }
}

function mapBusinessHours(calendar: BackendBusinessHours): BusinessHours {
  return {
    id: calendar.id,
    name: calendar.name,
    timezone: calendar.timezone,
    active: calendar.active,
    days: (calendar.days ?? []).map((day) => ({
      day: day.day,
      enabled: day.enabled,
      open: day.open,
      close: day.close,
    })),
    updatedAt: calendar.updated_at,
  }
}

function mapTicketTemplate(template: BackendTicketTemplate): TicketTemplate {
  return {
    id: template.id,
    name: template.name,
    subject: template.subject,
    description: template.description,
    priority: mapPriority(template.priority),
    channelId: normalizeChannelId(template.channel),
    group: template.group,
    tags: template.tags ?? [],
    active: template.active,
    updatedAt: template.updated_at,
  }
}

function mapTag(tag: BackendTag): Tag {
  return {
    id: tag.id,
    name: tag.name,
    color: tag.color,
    description: tag.description,
    active: tag.active,
    updatedAt: tag.updated_at,
  }
}

function mapCsatSurvey(survey: BackendCsatSurvey): CsatSurvey {
  return {
    id: survey.id,
    name: survey.name,
    question: survey.question,
    scale: survey.scale,
    channels: (survey.channels ?? []).map(normalizeChannelId),
    active: survey.active,
    updatedAt: survey.updated_at,
  }
}

function mapEmailNotification(notification: BackendEmailNotification): EmailNotification {
  return {
    id: notification.id,
    name: notification.name,
    event: notification.event,
    recipients: notification.recipients ?? [],
    subject: notification.subject,
    body: notification.body,
    active: notification.active,
    updatedAt: notification.updated_at,
  }
}

function mapScenarioAutomation(scenario: BackendScenarioAutomation): ScenarioAutomation {
  return {
    id: scenario.id,
    name: scenario.name,
    description: scenario.description,
    actions: (scenario.actions ?? []).map((action) => ({
      type: action.type,
      value: action.value,
    })),
    active: scenario.active,
    updatedAt: scenario.updated_at,
  }
}

function mapCustomFieldDefinition(field: BackendCustomFieldDefinition): CustomFieldDefinition {
  return {
    id: field.id,
    entity: field.entity,
    key: field.key,
    label: field.label,
    fieldType: field.field_type,
    required: field.required,
    active: field.active,
    options: field.options ?? [],
    helpText: field.help_text,
    position: field.position,
    updatedAt: field.updated_at,
  }
}

function mapCustomObject(object: BackendCustomObject): CustomObject {
  return {
    id: object.id,
    key: object.key,
    name: object.name,
    description: object.description,
    fields: (object.fields ?? []).map((field) => ({
      key: field.key,
      label: field.label,
      fieldType: field.field_type,
      required: field.required,
      options: field.options ?? [],
    })),
    active: object.active,
    updatedAt: object.updated_at,
  }
}

function mapProduct(product: BackendProduct): Product {
  return {
    id: product.id,
    name: product.name,
    code: product.code,
    description: product.description,
    active: product.active,
    updatedAt: product.updated_at,
  }
}

function mapSavedReport(report: BackendSavedReport): SavedReport {
  return {
    id: report.id,
    name: report.name,
    reportType: report.report_type,
    description: report.description,
    filters: report.filters ?? {},
    cadence: report.cadence,
    recipients: report.recipients ?? [],
    active: report.active,
    updatedAt: report.updated_at,
  }
}

function mapServiceAppointment(appointment: BackendServiceAppointment): ServiceAppointment {
  return {
    id: appointment.id,
    title: appointment.title,
    customerId: appointment.customer_id,
    technicianId: appointment.technician_id,
    scheduledAt: appointment.scheduled_at,
    durationMinutes: appointment.duration_minutes,
    status: appointment.status,
    location: appointment.location,
    notes: appointment.notes,
    updatedAt: appointment.updated_at,
  }
}

function mapDiscussionTopic(topic: BackendDiscussionTopic): DiscussionTopic {
  return {
    id: topic.id,
    title: topic.title,
    category: topic.category,
    body: topic.body,
    status: topic.status,
    pinned: topic.pinned,
    author: topic.author,
    replyCount: topic.reply_count,
    updatedAt: topic.updated_at,
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
  const topKnowledgeSuggestion = context.knowledge_suggestions?.[0]
  const macroSuggestions = context.macro_suggestions?.map(mapResponseMacroSuggestion) ?? []
  const topMacroSuggestion = macroSuggestions[0]
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
      topMacroSuggestion?.macro.body ||
      context.ticket.recommended_action ||
      'Acknowledge the customer, confirm ownership, and set the next update time.',
    suggestedArticle:
      topKnowledgeSuggestion?.article.title ??
      (context.company?.name
        ? `Resolution guidance for ${context.company.name}`
        : 'Customer response checklist'),
    escalation:
      settings.aiWorkQueueAutomationEnabled && latestDecision
        ? `AI queue decision ${latestDecision.decision_type} is active.`
        : 'Manual supervisor review required before escalation.',
    recommendedAction:
      context.ticket.recommended_action ||
      'Review the backend ticket context and confirm the next action.',
    confidence:
      Math.max(topKnowledgeSuggestion?.score ?? 0, topMacroSuggestion?.score ?? 0) ||
      Math.round((latestDecision?.confidence ?? 0.72) * 100),
    knowledgeReasons: topKnowledgeSuggestion?.reasons ?? [],
    responseMacros: macroSuggestions,
    duplicateSuggestions: context.duplicate_suggestions?.map(mapDuplicateTicketSuggestion) ?? [],
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
    caseId: context.ticket.case_id ?? null,
    createdAt: context.ticket.created_at,
    updatedAt: context.ticket.updated_at,
    resolvedAt: context.ticket.resolved_at ?? null,
    closedAt: context.ticket.closed_at ?? null,
    slaResolutionMet: context.ticket.sla_resolution_met ?? null,
    firstResponseDue: context.ticket.sla.first_response_due_at,
    resolutionDue: context.ticket.sla.resolution_due_at,
    slaState: mapSlaState(context.ticket),
    language: 'English',
    unread: latestTimeline?.authorRole === 'customer',
    tags: context.ticket.tags,
    customFields: context.ticket.custom_fields ?? {},
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
  const linkedConversation = handoff.linked_ticket_id
    ? conversationsById.get(handoff.linked_ticket_id)
    : undefined
  return {
    id: handoff.id,
    conversationId: handoff.ticket_id,
    linkedConversationId: linkedConversation?.id ?? handoff.linked_ticket_id ?? undefined,
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
          : handoff.status === 'in_progress'
            ? 'in-progress'
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

function mapCase(record: BackendCase): CaseRecord {
  return {
    id: record.id,
    publicId: record.public_id,
    customerId: record.customer_id,
    title: record.title,
    status: record.status,
    priority: mapPriority(record.priority),
    summary: record.summary,
    openedBy: record.opened_by,
    ticketIds: record.ticket_ids,
    channels: record.channels.map(normalizeChannelId),
    ticketCount: record.ticket_count,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
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

function mapResponseMacro(macro: BackendResponseMacro): ResponseMacro {
  return {
    id: macro.id,
    name: macro.name,
    body: macro.body,
    language: macro.language,
    channels: macro.channels.map(normalizeChannelId),
    tags: macro.tags,
    shortcut: macro.shortcut ?? undefined,
    active: macro.active,
    usageCount: macro.usage_count,
    lastUsedAt: macro.last_used_at ?? undefined,
    updatedAt: macro.updated_at,
  }
}

function mapResponseMacroSuggestion(suggestion: BackendResponseMacroSuggestion): ResponseMacroSuggestion {
  return {
    macro: mapResponseMacro(suggestion.macro),
    score: suggestion.score,
    reasons: suggestion.reasons,
    matchedTerms: suggestion.matched_terms,
  }
}

function mapDuplicateTicketSuggestion(
  suggestion: BackendDuplicateTicketSuggestion,
): DuplicateTicketSuggestion {
  return {
    ticketId: suggestion.ticket.id,
    ticketNumber: suggestion.ticket.public_id,
    subject: suggestion.ticket.subject,
    status: mapStatus(suggestion.ticket.status),
    priority: mapPriority(suggestion.ticket.priority),
    channelId: normalizeChannelId(suggestion.ticket.channel),
    customerName: suggestion.customer?.name ?? 'Unknown customer',
    customerEmail: suggestion.customer?.email ?? '',
    score: suggestion.score,
    reasons: suggestion.reasons,
    matchedTerms: suggestion.matched_terms,
    updatedAt: suggestion.ticket.updated_at,
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
  const cases = (snapshot.cases ?? []).map(mapCase)
  const supportGroups = (snapshot.support_groups ?? snapshot.supportGroups ?? []).map(mapSupportGroup)
  const slaPolicies = (snapshot.sla_policies ?? snapshot.slaPolicies ?? []).map(mapSlaPolicy)
  const businessHours = (snapshot.business_hours ?? snapshot.businessHours ?? []).map(mapBusinessHours)
  const ticketTemplates = (snapshot.ticket_templates ?? snapshot.ticketTemplates ?? []).map(
    mapTicketTemplate,
  )
  const tags = (snapshot.tags ?? []).map(mapTag)
  const csatSurveys = (snapshot.csat_surveys ?? snapshot.csatSurveys ?? []).map(mapCsatSurvey)
  const emailNotifications = (
    snapshot.email_notifications ??
    snapshot.emailNotifications ??
    []
  ).map(mapEmailNotification)
  const scenarioAutomations = (
    snapshot.scenario_automations ??
    snapshot.scenarioAutomations ??
    []
  ).map(mapScenarioAutomation)
  const customFieldDefinitions = (
    snapshot.custom_field_definitions ??
    snapshot.customFieldDefinitions ??
    []
  ).map(mapCustomFieldDefinition)
  const customObjects = (snapshot.custom_objects ?? snapshot.customObjects ?? []).map(mapCustomObject)
  const products = (snapshot.products ?? []).map(mapProduct)
  const savedReports = (snapshot.savedReports ?? []).map(mapSavedReport)
  const serviceAppointments = (snapshot.serviceAppointments ?? []).map(mapServiceAppointment)
  const discussionTopics = (snapshot.discussionTopics ?? []).map(mapDiscussionTopic)
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
    supportGroups,
    slaPolicies,
    businessHours,
    ticketTemplates,
    tags,
    csatSurveys,
    emailNotifications,
    scenarioAutomations,
    customFieldDefinitions,
    customObjects,
    products,
    savedReports,
    serviceAppointments,
    discussionTopics,
    articles: snapshot.knowledge.map(mapKnowledgeArticle),
    ticketFields: (snapshot.ticket_fields ?? snapshot.ticketFields ?? []).map(mapTicketField),
    responseMacros: snapshot.macros.map(mapResponseMacro),
    rules: snapshot.rules.map(mapRule),
    handoffs,
    cases,
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

function matchesSearch(conversation: OmniConversation, search: string, contactText = '') {
  const query = search.trim().toLowerCase()
  if (!query) return true
  const haystack = [
    conversation.ticketNumber,
    conversation.subject,
    conversation.preview,
    conversation.intent,
    conversation.group,
    conversation.tags.join(' '),
    contactText, // customer email + phone + contact-point values
  ]
    .join(' ')
    .toLowerCase()
  if (haystack.includes(query)) return true
  // Phone-style queries: compare digits-only so formatting (+, spaces, dashes) doesn't matter.
  const queryDigits = query.replace(/\D/g, '')
  if (queryDigits.length >= 6 && haystack.replace(/\D/g, '').includes(queryDigits)) return true
  return false
}

function filterConversation(conversation: OmniConversation, filters: InboxFilters, contactText = '') {
  return (
    (filters.channel === 'all' || conversation.channelId === filters.channel) &&
    (filters.status === 'all' || conversation.status === filters.status) &&
    (filters.priority === 'all' || conversation.priority === filters.priority) &&
    (filters.sla === 'all' || conversation.slaState === filters.sla) &&
    (filters.assignee === 'all' || conversation.assigneeId === filters.assignee) &&
    (filters.sentiment === 'all' || conversation.sentiment === filters.sentiment) &&
    matchesSearch(conversation, filters.search, contactText)
  )
}

async function fetchOptionalOidcProviderConfig() {
  try {
    return await fetchOidcProviderConfig()
  } catch {
    return undefined
  }
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
    if (!online) return
    let cancelled = false
    fetchOidcProviderConfig()
      .then((config) => {
        if (cancelled) return
        setBackendSync((current) => ({
          ...current,
          oidcProviderConfig: config,
        }))
      })
      .catch(() => undefined)

    return () => {
      cancelled = true
    }
  }, [online])

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

  async function applyBackendSession(session: BackendSession) {
    saveBackendSession(session)
    const [snapshot, oidcProviderConfig] = await Promise.all([
      fetchBackendSnapshot(session),
      fetchOptionalOidcProviderConfig(),
    ])
    const nextSession = sessionFromSnapshot(session, snapshot)
    if (sessionChanged(session, nextSession)) saveBackendSession(nextSession)
    patchState((current) => mergeBackendSnapshot(current, snapshot))
    setBackendSync((current) => ({
      ...current,
      status: 'connected',
      baseUrl: getBackendBaseUrl(),
      lastSyncAt: new Date().toISOString(),
      snapshot,
      oidcProviderConfig: oidcProviderConfig ?? current.oidcProviderConfig,
    }))
  }

  async function login(input: BackendLoginInput) {
    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))
    try {
      const session = await loginBackend(input)
      await applyBackendSession(session)
    } catch (error) {
      saveBackendSession(null)
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'Login failed',
      }))
    }
  }

  async function beginOidcLogin(marketId: string) {
    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))
    try {
      const returnTo =
        typeof window === 'undefined'
          ? undefined
          : `${window.location.origin}${window.location.pathname}`
      const start = await startOidcLoginBackend({ market_id: marketId, return_to: returnTo })
      window.location.assign(start.authorization_url)
      return true
    } catch (error) {
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'SSO login failed',
      }))
      return false
    }
  }

  async function completeOidcLogin(input: BackendOidcCallbackInput) {
    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))
    try {
      const session = await completeOidcLoginBackend(input)
      await applyBackendSession(session)
      return true
    } catch (error) {
      saveBackendSession(null)
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'SSO login failed',
      }))
      return false
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
    const market = backendSession.available_markets.find((item) => item.id === marketId)
    if (!market) {
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: 'You do not have access to that market.',
      }))
      return
    }
    const nextSession = { ...backendSession, market }
    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))
    try {
      await applyBackendSession(nextSession)
    } catch (error) {
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'Market switch failed',
      }))
    }
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
      const [snapshot, oidcProviderConfig] = await Promise.all([
        fetchBackendSnapshot(backendSession),
        fetchOptionalOidcProviderConfig(),
      ])
      const nextSession = sessionFromSnapshot(backendSession, snapshot)
      if (sessionChanged(backendSession, nextSession)) saveBackendSession(nextSession)
      patchState((current) => mergeBackendSnapshot(current, snapshot))
      setBackendSync((current) => ({
        ...current,
        status: 'connected',
        baseUrl: getBackendBaseUrl(),
        lastSyncAt: new Date().toISOString(),
        snapshot,
        oidcProviderConfig: oidcProviderConfig ?? current.oidcProviderConfig,
      }))
    } catch (error) {
      if (isBackendAuthError(error)) {
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

    Promise.all([fetchBackendSnapshot(backendSession), fetchOptionalOidcProviderConfig()])
      .then(([snapshot, oidcProviderConfig]) => {
        if (cancelled) return
        const nextSession = sessionFromSnapshot(backendSession, snapshot)
        if (sessionChanged(backendSession, nextSession)) saveBackendSession(nextSession)
        patchState((current) => mergeBackendSnapshot(current, snapshot))
        setBackendSync((current) => ({
          ...current,
          status: 'connected',
          baseUrl: getBackendBaseUrl(),
          lastSyncAt: new Date().toISOString(),
          snapshot,
          oidcProviderConfig: oidcProviderConfig ?? current.oidcProviderConfig,
        }))
      })
      .catch((error) => {
        if (cancelled) return
        if (isBackendAuthError(error)) {
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

  const customerContactIndex = useMemo(() => {
    const map = new Map<string, string>()
    for (const customer of state.customers) {
      const parts = [customer.email, customer.phone, ...(customer.contactMethods ?? []).map((m) => m.value)]
        .filter(Boolean)
        .join(' ')
      map.set(customer.id, parts)
    }
    return map
  }, [state.customers])

  const filteredConversations = useMemo(() => {
    return state.conversations
      .filter((conversation) =>
        filterConversation(conversation, state.filters, customerContactIndex.get(conversation.customerId) ?? ''),
      )
      .sort((a, b) => {
        const priorityScore: Record<Priority, number> = { urgent: 4, high: 3, medium: 2, low: 1 }
        const slaScore: Record<SlaState, number> = { breached: 4, risk: 3, healthy: 2, paused: 1 }
        return (
          slaScore[b.slaState] - slaScore[a.slaState] ||
          priorityScore[b.priority] - priorityScore[a.priority] ||
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        )
      })
  }, [state.conversations, state.filters, customerContactIndex])

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

  async function syncBackendMutation<T>(
    operation: (session: BackendSession) => Promise<T>,
    selection?: (result: T) => {
      screen?: ScreenId
      conversationId?: string
      customerId?: string
      channelId?: ChannelId | 'all'
    },
  ) {
    if (!online || !backendSession) {
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: !online
          ? 'Browser is offline. Backend writes resume when connectivity returns.'
          : 'Sign in before writing backend data.',
      }))
      return false
    }
    const session = backendSession

    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))

    try {
      const result = await operation(session)
      const snapshot = await fetchBackendSnapshot(session)
      commitBackendSnapshot(snapshot, selection?.(result))
      return true
    } catch (error) {
      if (isBackendAuthError(error)) {
        saveBackendSession(null)
      }
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'Backend write failed',
      }))
      return false
    }
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

  async function submitComposer(input: ComposerInput) {
    const trimmedBody = input.body.trim()
    if (!trimmedBody && !input.attachment) return

    const bodyWithAttachment = input.attachment
      ? [
          trimmedBody || 'Attachment added to the customer case.',
          `Attachment: ${input.attachment.filename} (${input.attachment.contentType}, ${Math.round(input.attachment.sizeBytes / 1024)} KB).`,
        ].join('\n')
      : trimmedBody
    const saveAttachment = (session: BackendSession) => {
      if (!input.attachment) return Promise.resolve()
      if (input.attachment.file) {
        return uploadBackendAttachment(input.conversationId, input.attachment.file, session)
      }
      return createBackendAttachment(
        input.conversationId,
        {
          filename: input.attachment.filename,
          content_type: input.attachment.contentType,
          size_bytes: input.attachment.sizeBytes,
        },
        session,
      )
    }

    if (input.mode === 'handoff') {
      if (
        await syncBackendMutation(
          async (session) => {
            await saveAttachment(session)
            return createBackendHandoff(
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
            )
          },
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
      await syncBackendMutation(
        async (session) => {
          await saveAttachment(session)
          return postBackendReply(
            input.conversationId,
            {
              channel: backendChannelId(input.channelId),
              actor: session.user.name,
              body: bodyWithAttachment,
              public: input.mode === 'reply',
            },
            session,
          )
        },
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
      body: bodyWithAttachment,
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
              context: bodyWithAttachment,
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
                body: bodyWithAttachment,
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

  async function createConversation(input: NewTicketInput) {
    if (
      await syncBackendMutation(
        (session) =>
          createBackendTicket(
            {
              subject: input.subject.trim(),
              description: input.body.trim(),
              customer_id: input.customerId,
              channel: backendChannelId(input.channelId),
              priority: backendPriority(input.priority),
              tags: ['new-request'],
              custom_fields: input.customFields ?? {},
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
        customFields: input.customFields ?? {},
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

  async function updateConversation(
    conversationId: string,
    patch: Partial<OmniConversation>,
    options?: { resolutionNote?: string; notifyCustomer?: boolean },
  ) {
    const backendPatch: {
      status?: BackendTicket['status']
      priority?: BackendTicket['priority']
      assignee_id?: string | null
      custom_fields?: Record<string, unknown>
      resolution_note?: string
      notify_customer?: boolean
    } = {}

    if (patch.status) backendPatch.status = backendStatus(patch.status)
    if (patch.priority) backendPatch.priority = backendPriority(patch.priority)
    if ('assigneeId' in patch) backendPatch.assignee_id = patch.assigneeId || null
    if ('customFields' in patch) backendPatch.custom_fields = patch.customFields
    if (options?.resolutionNote !== undefined) backendPatch.resolution_note = options.resolutionNote
    if (options?.notifyCustomer !== undefined) backendPatch.notify_customer = options.notifyCustomer

    if (
      Object.keys(backendPatch).length > 0 &&
      await syncBackendMutation(
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
    const conversation = state.conversations.find((item) => item.id === conversationId)
    const nextDone = !conversation?.tasks.find((task) => task.id === taskId)?.done

    const applyLocal = () =>
      patchState((current) => ({
        ...current,
        conversations: current.conversations.map((item) =>
          item.id === conversationId
            ? {
                ...item,
                tasks: item.tasks.map((task) =>
                  task.id === taskId ? { ...task, done: nextDone } : task,
                ),
                updatedAt: new Date().toISOString(),
              }
            : item,
        ),
      }))

    // Optimistic update, then persist the checklist item to the backend.
    applyLocal()
    if (online && backendSession) {
      void syncBackendMutation((session) =>
        patchBackendTicket(
          conversationId,
          { task_item_id: taskId, task_item_complete: nextDone },
          session,
        ),
      )
    }
  }

  async function toggleChannelIntake(channelId: ChannelId) {
    const channel = state.channels.find((item) => item.id === channelId)
    if (
      channel &&
      await syncBackendMutation((session) =>
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

  async function toggleRule(ruleId: string) {
    const rule = state.rules.find((item) => item.id === ruleId)
    if (
      rule &&
      await syncBackendMutation((session) =>
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

  async function publishArticle(articleId: string) {
    if (
      await syncBackendMutation((session) =>
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

  function createKnowledgeArticle(input: BackendCreateKnowledgeInput) {
    return syncBackendMutation((session) => createBackendKnowledgeArticle(input, session))
  }

  function updateKnowledgeArticle(articleId: string, patch: BackendUpdateKnowledgeInput) {
    return syncBackendMutation((session) =>
      patchBackendKnowledgeArticle(articleId, patch, session),
    )
  }

  function createCustomer(input: BackendCreateCustomerInput) {
    return syncBackendMutation(
      (session) => createBackendCustomer(input, session),
      (customer) => ({ screen: 'customers', customerId: customer.id }),
    )
  }

  function updateCustomer(customerId: string, patch: BackendUpdateCustomerInput) {
    return syncBackendMutation((session) => patchBackendCustomer(customerId, patch, session))
  }

  function createUser(input: BackendCreateUserInput) {
    return syncBackendMutation((session) => createBackendUser(input, session))
  }

  function updateUser(userId: string, patch: BackendUpdateUserInput) {
    return syncBackendMutation((session) => patchBackendUser(userId, patch, session))
  }

  function createSupportGroup(input: BackendCreateSupportGroupInput) {
    return syncBackendMutation((session) => createBackendSupportGroup(input, session))
  }

  function updateSupportGroup(groupId: string, patch: BackendUpdateSupportGroupInput) {
    return syncBackendMutation((session) => patchBackendSupportGroup(groupId, patch, session))
  }

  function createSlaPolicy(input: BackendCreateSlaPolicyInput) {
    return syncBackendMutation((session) => createBackendSlaPolicy(input, session))
  }

  function updateSlaPolicy(policyId: string, patch: BackendUpdateSlaPolicyInput) {
    return syncBackendMutation((session) => patchBackendSlaPolicy(policyId, patch, session))
  }

  function createBusinessHours(input: BackendCreateBusinessHoursInput) {
    return syncBackendMutation((session) => createBackendBusinessHours(input, session))
  }

  function updateBusinessHours(businessHoursId: string, patch: BackendUpdateBusinessHoursInput) {
    return syncBackendMutation((session) => patchBackendBusinessHours(businessHoursId, patch, session))
  }

  function createTicketTemplate(input: BackendCreateTicketTemplateInput) {
    return syncBackendMutation((session) => createBackendTicketTemplate(input, session))
  }

  function updateTicketTemplate(templateId: string, patch: BackendUpdateTicketTemplateInput) {
    return syncBackendMutation((session) => patchBackendTicketTemplate(templateId, patch, session))
  }

  function createTag(input: BackendCreateTagInput) {
    return syncBackendMutation((session) => createBackendTag(input, session))
  }

  function updateTag(tagId: string, patch: BackendUpdateTagInput) {
    return syncBackendMutation((session) => patchBackendTag(tagId, patch, session))
  }

  function createCsatSurvey(input: BackendCreateCsatSurveyInput) {
    return syncBackendMutation((session) => createBackendCsatSurvey(input, session))
  }

  function updateCsatSurvey(surveyId: string, patch: BackendUpdateCsatSurveyInput) {
    return syncBackendMutation((session) => patchBackendCsatSurvey(surveyId, patch, session))
  }

  function createEmailNotification(input: BackendCreateEmailNotificationInput) {
    return syncBackendMutation((session) => createBackendEmailNotification(input, session))
  }

  function updateEmailNotification(notificationId: string, patch: BackendUpdateEmailNotificationInput) {
    return syncBackendMutation((session) => patchBackendEmailNotification(notificationId, patch, session))
  }

  function createScenarioAutomation(input: BackendCreateScenarioAutomationInput) {
    return syncBackendMutation((session) => createBackendScenarioAutomation(input, session))
  }

  function updateScenarioAutomation(scenarioId: string, patch: BackendUpdateScenarioAutomationInput) {
    return syncBackendMutation((session) => patchBackendScenarioAutomation(scenarioId, patch, session))
  }

  function createCustomFieldDefinition(input: BackendCreateCustomFieldDefinitionInput) {
    return syncBackendMutation((session) => createBackendCustomFieldDefinition(input, session))
  }

  function updateCustomFieldDefinition(fieldId: string, patch: BackendUpdateCustomFieldDefinitionInput) {
    return syncBackendMutation((session) => patchBackendCustomFieldDefinition(fieldId, patch, session))
  }

  function createCustomObject(input: BackendCreateCustomObjectInput) {
    return syncBackendMutation((session) => createBackendCustomObject(input, session))
  }

  function updateCustomObject(objectId: string, patch: BackendUpdateCustomObjectInput) {
    return syncBackendMutation((session) => patchBackendCustomObject(objectId, patch, session))
  }

  function createProduct(input: BackendCreateProductInput) {
    return syncBackendMutation((session) => createBackendProduct(input, session))
  }

  function updateProduct(productId: string, patch: BackendUpdateProductInput) {
    return syncBackendMutation((session) => patchBackendProduct(productId, patch, session))
  }

  function createSavedReport(input: BackendCreateSavedReportInput) {
    return syncBackendMutation((session) => createBackendSavedReport(input, session))
  }

  function updateSavedReport(reportId: string, patch: BackendUpdateSavedReportInput) {
    return syncBackendMutation((session) => patchBackendSavedReport(reportId, patch, session))
  }

  function createServiceAppointment(input: BackendCreateServiceAppointmentInput) {
    return syncBackendMutation((session) => createBackendServiceAppointment(input, session))
  }

  function updateServiceAppointment(
    appointmentId: string,
    patch: BackendUpdateServiceAppointmentInput,
  ) {
    return syncBackendMutation((session) =>
      patchBackendServiceAppointment(appointmentId, patch, session),
    )
  }

  function createDiscussionTopic(input: BackendCreateDiscussionTopicInput) {
    return syncBackendMutation((session) => createBackendDiscussionTopic(input, session))
  }

  function updateDiscussionTopic(topicId: string, patch: BackendUpdateDiscussionTopicInput) {
    return syncBackendMutation((session) => patchBackendDiscussionTopic(topicId, patch, session))
  }

  function createTicketField(input: BackendCreateTicketFieldInput) {
    return syncBackendMutation((session) => createBackendTicketField(input, session))
  }

  function updateTicketField(fieldId: string, patch: BackendUpdateTicketFieldInput) {
    return syncBackendMutation((session) => patchBackendTicketField(fieldId, patch, session))
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

  async function enrollMfa(): Promise<BackendMfaEnrollment | null> {
    if (!online || !backendSession) return null
    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))
    try {
      const enrollment = await enrollBackendMfa(backendSession)
      setBackendSync((current) => ({
        ...current,
        status: 'connected',
        lastSyncAt: new Date().toISOString(),
      }))
      return enrollment
    } catch (error) {
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'MFA enrollment failed',
      }))
      return null
    }
  }

  async function confirmMfa(code: string) {
    if (!online || !backendSession) return false
    const session = backendSession
    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))
    try {
      const user = await confirmBackendMfa({ code }, session)
      const nextSession = { ...session, user }
      saveBackendSession(nextSession)
      const snapshot = await fetchBackendSnapshot(nextSession)
      commitBackendSnapshot(snapshot)
      return true
    } catch (error) {
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'MFA confirmation failed',
      }))
      return false
    }
  }

  async function disableMfa(currentPassword: string, code?: string) {
    if (!online || !backendSession) return false
    const session = backendSession
    setBackendSync((current) => ({
      ...current,
      status: 'syncing',
      error: undefined,
    }))
    try {
      const user = await disableBackendMfa(
        {
          current_password: currentPassword,
          code: code || undefined,
        },
        session,
      )
      const nextSession = { ...session, user }
      saveBackendSession(nextSession)
      const snapshot = await fetchBackendSnapshot(nextSession)
      commitBackendSnapshot(snapshot)
      return true
    } catch (error) {
      setBackendSync((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'MFA disable failed',
      }))
      return false
    }
  }

  function retryOutboundMessage(messageId: string) {
    return syncBackendMutation((session) => retryBackendOutboundMessage(messageId, session))
  }

  function updateOperationalAlertStatus(
    alertId: string,
    status: BackendOperationalAlertStatus,
    note?: string,
  ) {
    return syncBackendMutation((session) =>
      patchBackendOperationalAlert(
        alertId,
        {
          status,
          note,
        },
        session,
      ),
    )
  }

  async function updateHandoffStatus(handoffId: string, status: HandoffStatus) {
    const backendStatusValue =
      status === 'completed' ? 'resolved' : status === 'in-progress' ? 'in_progress' : status

    if (
      await syncBackendMutation((session) =>
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

  async function createCase(input: {
    customerId: string
    title: string
    ticketIds?: string[]
    summary?: string
  }) {
    return syncBackendMutation((session) =>
      createBackendCase(
        {
          customer_id: input.customerId,
          title: input.title,
          ticket_ids: input.ticketIds ?? [],
          summary: input.summary ?? '',
        },
        session,
      ),
    )
  }

  async function attachCaseTicket(caseId: string, ticketId: string) {
    return syncBackendMutation((session) => attachBackendCaseTicket(caseId, ticketId, session))
  }

  async function detachCaseTicket(caseId: string, ticketId: string) {
    return syncBackendMutation((session) => detachBackendCaseTicket(caseId, ticketId, session))
  }

  async function setCaseStatus(caseId: string, status: CaseRecord['status']) {
    return syncBackendMutation((session) => updateBackendCase(caseId, { status }, session))
  }

  async function toggleHandoffChecklist(handoffId: string, taskId: string) {
    const handoff = state.handoffs.find((item) => item.id === handoffId)
    const task = handoff?.checklist.find((item) => item.id === taskId)
    if (
      handoff &&
      task &&
      await syncBackendMutation((session) =>
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

  function recordResponseMacroUse(macroId: string, ticketId: string) {
    return syncBackendMutation((session) => recordBackendResponseMacroUse(macroId, ticketId, session))
  }

  function createResponseMacro(input: BackendCreateResponseMacroInput) {
    return syncBackendMutation((session) => createBackendResponseMacro(input, session))
  }

  function updateResponseMacro(macroId: string, patch: BackendUpdateResponseMacroInput) {
    return syncBackendMutation((session) => patchBackendResponseMacro(macroId, patch, session))
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
    createKnowledgeArticle,
    updateKnowledgeArticle,
    createCustomer,
    updateCustomer,
    createUser,
    updateUser,
    createSupportGroup,
    updateSupportGroup,
    createSlaPolicy,
    updateSlaPolicy,
    createBusinessHours,
    updateBusinessHours,
    createTicketTemplate,
    updateTicketTemplate,
    createTag,
    updateTag,
    createCsatSurvey,
    updateCsatSurvey,
    createEmailNotification,
    updateEmailNotification,
    createScenarioAutomation,
    updateScenarioAutomation,
    createCustomFieldDefinition,
    updateCustomFieldDefinition,
    createCustomObject,
    updateCustomObject,
    createProduct,
    updateProduct,
    createSavedReport,
    updateSavedReport,
    createServiceAppointment,
    updateServiceAppointment,
    createDiscussionTopic,
    updateDiscussionTopic,
    createTicketField,
    updateTicketField,
    changePassword,
    enrollMfa,
    confirmMfa,
    disableMfa,
    retryOutboundMessage,
    updateOperationalAlertStatus,
    updateSettings,
    updateHandoffStatus,
    toggleHandoffChecklist,
    createCase,
    attachCaseTicket,
    detachCaseTicket,
    setCaseStatus,
    recordResponseMacroUse,
    createResponseMacro,
    updateResponseMacro,
    resetDemo,
    backendSession,
    login,
    beginOidcLogin,
    completeOidcLogin,
    logout,
    switchMarket,
    backendSync,
    refreshBackend,
  }
}
