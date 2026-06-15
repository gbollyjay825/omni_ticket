import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bell,
  BookOpen,
  CalendarClock,
  Bot,
  Building2,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Clock,
  Code2,
  Command,
  DatabaseZap,
  Download,
  Filter,
  Gauge,
  GitBranch,
  Globe2,
  Handshake,
  Headphones,
  Inbox,
  Languages,
  Layers,
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
  Star,
  UserCheck,
  Users,
  Wifi,
  WifiOff,
  Workflow,
  Wrench,
  X,
} from 'lucide-react'
import type {
  AttachmentDraft,
  BusinessHours,
  BusinessHoursDay,
  ChannelId,
  ComposerMode,
  ContactMethod,
  ConversationStatus,
  DiscussionTopic,
  DuplicateTicketSuggestion,
  HandoffStatus,
  KnowledgeArticle,
  NewTicketInput,
  OmniConversation,
  Priority,
  ResponseMacro,
  ResponseMacroSuggestion,
  ScreenId,
  Sentiment,
  SlaState,
  Tag,
  CsatSurvey,
  EmailNotification,
  ScenarioAction,
  ScenarioAutomation,
  CustomFieldDefinition,
  CustomObject,
  CustomObjectField,
  Product,
  SavedReport,
  ServiceAppointment,
  TicketField,
  TicketFieldType,
  TicketTemplate,
} from './domain'
import type {
  BackendAuditExportFormat,
  BackendAttachmentProviderConfig,
  BackendAttachmentRetentionPolicy,
  BackendAuditRetentionPolicy,
  BackendCreateSlaPolicyInput,
  BackendCreatePortalTicketInput,
  BackendCustomer,
  BackendDiscussionComment,
  BackendEmailProviderSettings,
  BackendGlobalSearchResult,
  BackendAnalyticsSummary,
  BackendIntegrationCredentialSettings,
  BackendMfaEnrollment,
  BackendOperationalAlert,
  BackendOperationalAlertStatus,
  BackendPermission,
  BackendPermissionProfile,
  BackendPortalAnswerSuggestion,
  BackendPortalTicketDetail,
  BackendProductionAccountReference,
  BackendProductionAccountReferenceDocs,
  BackendProductionAccountReferenceStatus,
  BackendProductionAccountRequestDelivery,
  BackendProductionAccountRequestPack,
  BackendProductionReadinessChecklist,
  BackendSsoProviderSettings,
  BackendTicketField,
  BackendUser,
  BackendUpdateEmailProviderSettingsInput,
  BackendUpdateIntegrationCredentialSettingsInput,
  BackendUpdateSsoProviderSettingsInput,
  BackendWidgetSettings,
} from './backend'
import {
  createBackendDiscussionComment,
  fetchBackendDiscussionComments,
  createBackendPortalTicket,
  createBackendPortalTicketReply,
  exportBackendAudit,
  createBackendProductionAccountReference,
  fetchBackendGlobalSearch,
  fetchBackendAnalyticsSummary,
  fetchBackendAttachmentRetentionPolicy,
  fetchBackendAuditRetentionPolicy,
  fetchBackendProductionAccountReferenceDocs,
  fetchBackendProductionAccountReferences,
  fetchBackendProductionAccountRequests,
  fetchBackendProductionReadinessChecklist,
  fetchBackendPortalAnswers,
  fetchBackendPortalTicket,
  mergeBackendTickets,
  patchBackendEmailSettings,
  patchBackendIntegrationCredentialSettings,
  patchBackendSettings,
  patchBackendSsoSettings,
  patchBackendWidgetSettings,
  patchBackendProductionAccountReference,
  pruneBackendAttachmentRetention,
  pruneBackendAuditRetention,
  sendBackendProductionAccountRequestEmail,
  uploadBackendPortalAttachment,
} from './backend'
import { useOmniStore } from './store'
import { DASHBOARD_RANGES, formatDuration, resolutionSeconds } from './metrics'
import type { DashboardRange } from './metrics'
import './App.css'

interface DashboardTodo {
  id: string
  label: string
  done: boolean
}

const TODO_STORAGE_PREFIX = 'omni.dashboard.todos:'

function makeTodoId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `todo-${Math.random().toString(36).slice(2)}`
}

function loadDashboardTodos(userId: string): DashboardTodo[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(`${TODO_STORAGE_PREFIX}${userId}`)
    if (!raw) return []
    const parsed = JSON.parse(raw) as DashboardTodo[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveDashboardTodos(userId: string, todos: DashboardTodo[]): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(`${TODO_STORAGE_PREFIX}${userId}`, JSON.stringify(todos))
  } catch {
    // Ignore storage write failures (private mode / quota); the widget still works in-session.
  }
}

const WATCH_STORAGE_PREFIX = 'omni.watched.tickets:'

function loadWatchedTickets(userId: string): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(`${WATCH_STORAGE_PREFIX}${userId}`)
    if (!raw) return []
    const parsed = JSON.parse(raw) as string[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveWatchedTickets(userId: string, ids: string[]): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(`${WATCH_STORAGE_PREFIX}${userId}`, JSON.stringify(ids))
  } catch {
    // Ignore storage write failures; watch state still works in-session.
  }
}

interface TicketTimeLog {
  id: string
  minutes: number
  agent: string
  at: string
}

const TIMELOG_STORAGE_KEY = 'omni.ticket.timelogs'

function loadTimeLogs(): Record<string, TicketTimeLog[]> {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(TIMELOG_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, TicketTimeLog[]>
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function saveTimeLogs(logs: Record<string, TicketTimeLog[]>): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(TIMELOG_STORAGE_KEY, JSON.stringify(logs))
  } catch {
    // Ignore storage write failures; time logs still work in-session.
  }
}

const screenConfig: { id: ScreenId; label: string; icon: LucideIcon }[] = [
  { id: 'command', label: 'Dashboard', icon: Command },
  { id: 'inbox', label: 'Tickets', icon: Inbox },
  { id: 'channels', label: 'Omnichat', icon: MessageCircle },
  { id: 'customers', label: 'Contacts', icon: Users },
  { id: 'knowledge', label: 'Solutions', icon: BookOpen },
  { id: 'automation', label: 'Workflows', icon: Workflow },
  { id: 'handoffs', label: 'Team Handoffs', icon: Handshake },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  { id: 'workforce', label: 'Scheduling dashboard', icon: UserCheck },
  { id: 'admin', label: 'Admin', icon: Settings },
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
  command: 'Omnichannel Dashboard with ticket trends, chat trends, CSAT, agents, to-do, and recent activity.',
  inbox: 'Familiar ticket views, filters, ticket details, reply, note, forward, linked work, and time logs.',
  channels: 'Omnichat Team Inbox, dashboard, campaigns, people, reports, marketplace, settings, and AI Studio.',
  customers: 'Omni Contacts view with customer profile, value, history, mood, and preferred contact routes.',
  knowledge: 'Solutions and reusable answers agents can apply to resolve faster and reduce repeat work.',
  automation: 'Workflows, SLA policies, automations, notifications, CSAT surveys, and proactive outreach.',
  handoffs: 'Cross-team work with owner, due time, blockers, and closure checklist.',
  analytics: 'Omni Analytics report catalog, saved reports, scheduled exports, and live service signals.',
  workforce: 'Service tasks, technician availability, appointment duration, and dispatch coverage.',
  admin: 'Omni Admin categories for team, channels, workflows, productivity, operations, and account controls.',
  portal: 'Customer self-service for answer deflection and ticket intake.',
  tracker: 'What is complete, what is pending, and what remains before production buildout.',
}
const handoffTeams = [
  'Billing Operations',
  'Fulfillment',
  'Engineering',
  'Account Operations',
  'Compliance',
]
const userRoleOptions = ['agent', 'supervisor', 'admin', 'auditor', 'service_account'] as const
const ticketFieldTypeOptions: TicketFieldType[] = [
  'text',
  'textarea',
  'select',
  'multiselect',
  'checkbox',
  'number',
  'date',
]
const setupSectionOptions = [
  { id: 'people', label: 'People' },
  { id: 'forms', label: 'Ticket forms' },
  { id: 'governance', label: 'Governance' },
  { id: 'connectors', label: 'Connectors' },
  { id: 'automation', label: 'Automation' },
] as const
type SetupSectionId = (typeof setupSectionOptions)[number]['id']
type TicketDetailTab = 'activities' | 'threads' | 'linked' | 'time'
type ChannelConsoleView =
  | 'inbox'
  | 'dashboard'
  | 'campaigns'
  | 'people'
  | 'reports'
  | 'marketplace'
  | 'settings'
  | 'ai-studio'
type AnalyticsReportGroup = 'catalog' | 'saved' | 'scheduled'
const freshdeskTicketActionItems = [
  { id: 'watch', label: 'Watch', shortcut: 'w', icon: Bell },
  { id: 'reply', label: 'Reply', shortcut: 'r', icon: Send },
  { id: 'note', label: 'Note', shortcut: 'n', icon: ClipboardList },
  { id: 'forward', label: 'Forward', shortcut: 'f', icon: Mail },
  { id: 'child', label: 'Child task', shortcut: '', icon: GitBranch },
  { id: 'close-silent', label: 'Close no email', shortcut: 'c', icon: CheckCircle2 },
] as const
const freshchatConsoleViews: { id: ChannelConsoleView; label: string; icon: LucideIcon }[] = [
  { id: 'inbox', label: 'Team Inbox', icon: Inbox },
  { id: 'dashboard', label: 'Dashboard', icon: Gauge },
  { id: 'campaigns', label: 'Campaigns', icon: Workflow },
  { id: 'people', label: 'People', icon: Users },
  { id: 'reports', label: 'Reports', icon: BarChart3 },
  { id: 'marketplace', label: 'Marketplace', icon: DatabaseZap },
  { id: 'settings', label: 'Settings', icon: Settings },
  { id: 'ai-studio', label: 'AI Studio', icon: Bot },
]
const setupModuleCatalog: Record<SetupSectionId, { title: string; modules: string[] }[]> = {
  people: [
    { title: 'Team', modules: ['Agents', 'Groups', 'Roles', 'Business hours', 'Profile settings'] },
    { title: 'Security', modules: ['MFA', 'Enterprise SSO', 'Permission profiles', 'Market access', 'API status'] },
  ],
  forms: [
    { title: 'Ticket setup', modules: ['Ticket fields', 'Ticket forms', 'Contact fields', 'Company fields', 'Custom objects'] },
    { title: 'Products', modules: ['Multiple products', 'Advanced ticketing', 'Portal branding', 'Purchase history'] },
  ],
  governance: [
    { title: 'Operations', modules: ['Audit export', 'Retention', 'Attachment lifecycle', 'Operational alerts', 'Scheduled exports'] },
    { title: 'Support ops', modules: ['Forums', 'Field service scheduling', 'Security controls', 'Helpdesk settings'] },
  ],
  connectors: [
    { title: 'Channels', modules: ['Email', 'Widgets', 'Phone', 'Omnichat', 'WhatsApp', 'Facebook', 'Feedback form'] },
    { title: 'Accounts', modules: ['Provider credentials', 'Marketplace apps', 'Account exports', 'Production account pack'] },
  ],
  automation: [
    { title: 'Workflows', modules: ['SLA policies', 'Automations', 'Email notifications', 'CSAT surveys', 'Proactive outreach'] },
    { title: 'Productivity', modules: ['Canned responses', 'Ticket templates', 'Scenario automations', 'Canned forms', 'Tags', 'Threads'] },
  ],
}
// Admin-catalog modules that map to a real, configurable Setup panel today. Only these
// render as clickable tiles so nothing in the catalog is a dead link; the rest land here
// as we build their panels (B-112/B-113).
const scenarioActionTypes: { value: string; label: string }[] = [
  { value: 'add_tag', label: 'Add tag' },
  { value: 'set_priority', label: 'Set priority' },
  { value: 'set_status', label: 'Set status' },
  { value: 'assign_group', label: 'Assign group' },
  { value: 'add_note', label: 'Add note' },
]

function scenarioActionLabel(type: string): string {
  return scenarioActionTypes.find((option) => option.value === type)?.label ?? titleCase(type.replace(/_/g, ' '))
}

const setupBuiltModules = new Set<string>([
  'Agents',
  'Groups',
  'Business hours',
  'Roles',
  'Permission profiles',
  'MFA',
  'Enterprise SSO',
  'Market access',
  'API status',
  'Ticket fields',
  'Ticket forms',
  'Contact fields',
  'Company fields',
  'Audit export',
  'Retention',
  'Attachment lifecycle',
  'Operational alerts',
  'Email',
  'Provider credentials',
  'Production account pack',
  'SLA policies',
  'Automations',
  'Canned responses',
  'Ticket templates',
  'Tags',
  'CSAT surveys',
  'Email notifications',
  'Scenario automations',
  'Custom objects',
  'Multiple products',
  'Proactive outreach',
  'Phone',
  'Marketplace apps',
  'Field service scheduling',
  'Account exports',
  'Scheduled exports',
  'Profile settings',
  'Security controls',
  'Threads',
  'Portal branding',
  'Helpdesk settings',
  'WhatsApp',
  'Facebook',
  'Feedback form',
  'Omnichat',
  'Forums',
  'Widgets',
  'Canned forms',
])
// Focused-hub: maps each catalog tool to the in-page panel it opens (the panel's
// data-setup-panel value). Tools absent here open a dedicated screen instead
// (see screenRoutes in openSetupModule).
const setupToolPanel: Record<string, string> = {
  // People (one workspace panel with internal sub-views)
  Agents: 'people',
  Groups: 'people',
  Roles: 'people',
  'Business hours': 'people',
  'Profile settings': 'people',
  MFA: 'people',
  'Enterprise SSO': 'people',
  'Permission profiles': 'people',
  'Market access': 'people',
  'API status': 'people',
  'Security controls': 'people',
  // Ticket forms
  'Ticket fields': 'forms-fields',
  'Ticket forms': 'forms-fields',
  'Contact fields': 'custom-fields',
  'Company fields': 'custom-fields',
  'Custom objects': 'custom-objects',
  'Multiple products': 'products',
  'Portal branding': 'branding',
  'Helpdesk settings': 'branding',
  // Governance
  Forums: 'forums',
  'Audit export': 'audit',
  'Account exports': 'audit',
  Retention: 'attachment',
  'Attachment lifecycle': 'attachment',
  'Operational alerts': 'alerts',
  // Connectors
  Widgets: 'widget',
  'Provider credentials': 'credentials',
  Phone: 'credentials',
  WhatsApp: 'credentials',
  Facebook: 'credentials',
  'Marketplace apps': 'credentials',
  Email: 'email',
  'Team inboxes': 'email',
  'Production account pack': 'production',
  // Automation
  'SLA policies': 'sla',
  Automations: 'automations',
  'Email notifications': 'email-notifications',
  'CSAT surveys': 'csat',
  'Feedback form': 'csat',
  'Proactive outreach': 'scenario',
  'Scenario automations': 'scenario',
  'Canned responses': 'canned',
  'Canned forms': 'templates',
  'Ticket templates': 'templates',
  Tags: 'tags',
}
// Which Setup section actually hosts each panel (a tool's tile may be listed under
// a different section than where its panel renders).
const setupPanelSection: Record<string, SetupSectionId> = {
  people: 'people',
  'forms-fields': 'forms',
  'custom-fields': 'forms',
  'custom-objects': 'forms',
  products: 'forms',
  branding: 'forms',
  forums: 'governance',
  audit: 'governance',
  attachment: 'governance',
  alerts: 'governance',
  widget: 'connectors',
  credentials: 'connectors',
  email: 'connectors',
  production: 'connectors',
  sla: 'automation',
  automations: 'automation',
  'email-notifications': 'automation',
  csat: 'automation',
  scenario: 'automation',
  canned: 'automation',
  templates: 'automation',
  tags: 'automation',
}
const analyticsReportCatalog: Record<AnalyticsReportGroup, { title: string; detail: string; badge: string }[]> = {
  catalog: [
    { title: 'Omnichannel Dashboard', detail: 'Tickets, chats, CSAT, available agents, and today filters.', badge: 'Live' },
    { title: 'Chat Analytics', detail: 'Speed of response, SLA metrics, conversation volume, and wait time.', badge: 'Chat' },
    { title: 'Team Performance', detail: 'Agent load, resolution movement, first response, and quality signals.', badge: 'Team' },
    { title: 'Customer Satisfaction', detail: 'Ticket CSAT, chat CSAT, feedback comments, and trend movement.', badge: 'CSAT' },
    { title: 'AI Agent Analytics', detail: 'Bot deflection, handoff reasons, session consumption, and answer gaps.', badge: 'AI' },
  ],
  saved: [
    { title: 'Executive service review', detail: 'Saved leadership view across open work and breached promises.', badge: 'Saved' },
    { title: 'Refund desk backlog', detail: 'Refund group backlog, average handling time, and overdue work.', badge: 'Saved' },
    { title: 'Market channel health', detail: 'NG, GH, UK, and Dubai channel readiness with queue load.', badge: 'Saved' },
  ],
  scheduled: [
    { title: 'Daily service digest', detail: 'Queued at 08:00 with tickets, chats, breaches, and blockers.', badge: 'Email' },
    { title: 'Weekly CSAT board', detail: 'Every Monday with CSAT, feedback themes, and agent availability.', badge: 'Email' },
    { title: 'Monthly export pack', detail: 'Audit-safe CSV and JSON exports for operations reporting.', badge: 'Export' },
  ],
}
const productionReferenceStatusOptions: BackendProductionAccountReferenceStatus[] = [
  'requested',
  'provisioned',
  'connected',
  'blocked',
  'retired',
]
type EmailSettingsDraft = {
  inboundEnabled: boolean
  inboundHost: string
  inboundPort: number
  inboundUsername: string
  inboundPassword: string
  inboundMailbox: string
  inboundUseSsl: boolean
  inboundMarkSeen: boolean
  clearInboundPassword: boolean
  outboundEnabled: boolean
  outboundHost: string
  outboundPort: number
  outboundUsername: string
  outboundPassword: string
  outboundFromEmail: string
  outboundUseStarttls: boolean
  outboundUseSsl: boolean
  clearOutboundPassword: boolean
}
const defaultEmailSettingsDraft: EmailSettingsDraft = {
  inboundEnabled: false,
  inboundHost: '',
  inboundPort: 993,
  inboundUsername: '',
  inboundPassword: '',
  inboundMailbox: 'INBOX',
  inboundUseSsl: true,
  inboundMarkSeen: true,
  clearInboundPassword: false,
  outboundEnabled: false,
  outboundHost: '',
  outboundPort: 587,
  outboundUsername: '',
  outboundPassword: '',
  outboundFromEmail: '',
  outboundUseStarttls: true,
  outboundUseSsl: false,
  clearOutboundPassword: false,
}
type IntegrationCredentialDraft = {
  aiProvider: string
  anthropicApiKey: string
  anthropicApiBaseUrl: string
  anthropicModel: string
  clearAnthropicApiKey: boolean
  alertWebhookUrl: string
  alertWebhookSecret: string
  alertDeliveryMinSeverity: 'info' | 'warning' | 'critical'
  clearAlertWebhookSecret: boolean
  smsHttpEndpoint: string
  smsHttpAuthToken: string
  smsHttpFrom: string
  smsHttpAuthHeader: string
  smsHttpAuthScheme: string
  smsHttpDeliveryCallbackUrl: string
  clearSmsHttpAuthToken: boolean
  voiceHttpEndpoint: string
  voiceHttpAuthToken: string
  voiceHttpFrom: string
  voiceHttpAuthHeader: string
  voiceHttpAuthScheme: string
  voiceHttpStatusCallbackUrl: string
  clearVoiceHttpAuthToken: boolean
  whatsappCloudApiBaseUrl: string
  whatsappPhoneNumberId: string
  whatsappAccessToken: string
  whatsappPreviewUrls: boolean
  clearWhatsappAccessToken: boolean
  facebookGraphApiBaseUrl: string
  facebookPageId: string
  facebookPageAccessToken: string
  facebookMessagingType: string
  clearFacebookPageAccessToken: boolean
  instagramGraphApiBaseUrl: string
  instagramBusinessAccountId: string
  instagramAccessToken: string
  clearInstagramAccessToken: boolean
}
const defaultIntegrationCredentialDraft: IntegrationCredentialDraft = {
  aiProvider: 'auto',
  anthropicApiKey: '',
  anthropicApiBaseUrl: 'https://api.anthropic.com',
  anthropicModel: 'claude-sonnet-4-6',
  clearAnthropicApiKey: false,
  alertWebhookUrl: '',
  alertWebhookSecret: '',
  alertDeliveryMinSeverity: 'warning',
  clearAlertWebhookSecret: false,
  smsHttpEndpoint: '',
  smsHttpAuthToken: '',
  smsHttpFrom: '',
  smsHttpAuthHeader: 'Authorization',
  smsHttpAuthScheme: 'Bearer',
  smsHttpDeliveryCallbackUrl: '',
  clearSmsHttpAuthToken: false,
  voiceHttpEndpoint: '',
  voiceHttpAuthToken: '',
  voiceHttpFrom: '',
  voiceHttpAuthHeader: 'Authorization',
  voiceHttpAuthScheme: 'Bearer',
  voiceHttpStatusCallbackUrl: '',
  clearVoiceHttpAuthToken: false,
  whatsappCloudApiBaseUrl: 'https://graph.facebook.com/v25.0',
  whatsappPhoneNumberId: '',
  whatsappAccessToken: '',
  whatsappPreviewUrls: false,
  clearWhatsappAccessToken: false,
  facebookGraphApiBaseUrl: 'https://graph.facebook.com/v25.0',
  facebookPageId: '',
  facebookPageAccessToken: '',
  facebookMessagingType: 'RESPONSE',
  clearFacebookPageAccessToken: false,
  instagramGraphApiBaseUrl: 'https://graph.instagram.com/v25.0',
  instagramBusinessAccountId: '',
  instagramAccessToken: '',
  clearInstagramAccessToken: false,
}
const permissionProfileOptions: BackendPermissionProfile[] = [
  'role_default',
  'read_only',
  'operations',
  'supervisor',
  'admin',
  'custom',
]
const permissionOptions: { value: BackendPermission; label: string }[] = [
  { value: 'operations.write', label: 'Operations write' },
  { value: 'supervisor.control', label: 'Supervisor tools' },
  { value: 'audit.read', label: 'Audit read' },
  { value: 'setup.manage', label: 'Setup manage' },
]
const portalMarketOptions = [
  { code: 'ng', label: 'NG · Nigeria' },
  { code: 'gh', label: 'GH · Ghana' },
  { code: 'uk', label: 'UK · United Kingdom' },
]
const portalPriorityOptions: NonNullable<BackendCreatePortalTicketInput['priority']>[] = [
  'normal',
  'high',
  'urgent',
  'low',
]

function userHasPermission(user: BackendUser, permission: BackendPermission) {
  if (Array.isArray(user.effective_permissions)) {
    return user.effective_permissions.includes(permission)
  }
  if (user.role === 'admin') return true
  if (permission === 'audit.read') return user.role === 'supervisor' || user.role === 'auditor'
  if (permission === 'supervisor.control') return user.role === 'supervisor'
  if (permission === 'operations.write') {
    return user.role === 'agent' || user.role === 'supervisor' || user.role === 'service_account'
  }
  return false
}

function userPermissionCount(user: BackendUser) {
  if (Array.isArray(user.effective_permissions)) return user.effective_permissions.length
  return permissionOptions.filter((permission) => userHasPermission(user, permission.value)).length
}

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
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function backendChannelId(value: ChannelId) {
  return value === 'phone' ? 'voice' : value
}

function backendPriorityId(value: Priority): NonNullable<BackendCreateSlaPolicyInput['priority']> {
  return value === 'medium' ? 'normal' : value
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

function relativeWorkTime(value: string) {
  const deltaMs = Date.now() - new Date(value).getTime()
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  if (Number.isNaN(deltaMs)) return formatTime(value)
  if (deltaMs < minute) return 'a few seconds ago'
  if (deltaMs < hour) {
    const minutes = Math.max(1, Math.round(deltaMs / minute))
    return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  }
  if (deltaMs < day) {
    const hours = Math.max(1, Math.round(deltaMs / hour))
    return `${hours} hour${hours === 1 ? '' : 's'} ago`
  }
  const days = Math.max(1, Math.round(deltaMs / day))
  return `${days} day${days === 1 ? '' : 's'} ago`
}

function formatFileSize(value: number) {
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  if (value >= 1024) return `${Math.max(1, Math.round(value / 1024))} KB`
  return `${value} B`
}

function percent(value: number, total: number) {
  return total === 0 ? 0 : Math.round((value / total) * 100)
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

function operationalAlertStatusTone(status: BackendOperationalAlert['status']) {
  if (status === 'resolved') return 'done'
  if (status === 'acknowledged') return 'pending'
  return 'risk'
}

function operationalAlertEntityLabel(alert: BackendOperationalAlert) {
  return `${titleCase(alert.entity_type)} · ${alert.entity_id}`
}

function productionRequestTone(status: string) {
  if (status === 'ready') return 'done'
  if (status === 'blocked') return 'risk'
  if (status === 'missing') return 'risk'
  return 'pending'
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
    createUser,
    updateUser,
    createSupportGroup,
    updateSupportGroup,
    createSlaPolicy,
    updateSlaPolicy,
    createBusinessHours,
    updateBusinessHours,
    createResponseMacro,
    updateResponseMacro,
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
    createKnowledgeArticle,
    updateKnowledgeArticle,
    createCustomer,
    updateCustomer,
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
    recordResponseMacroUse,
    resetDemo,
    backendSession,
    login,
    beginOidcLogin,
    completeOidcLogin,
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
  const [announcementDismissed, setAnnouncementDismissed] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [navExpanded, setNavExpanded] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true
    const stored = window.localStorage.getItem('omni-nav-expanded')
    return stored === null ? true : stored === 'true'
  })
  const [directChatFilter, setDirectChatFilter] = useState<'all' | 'open' | 'resolved'>('all')
  const [quickCreateOpen, setQuickCreateOpen] = useState(false)
  const [notificationOpen, setNotificationOpen] = useState(false)
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false)
  const [globalSearchResults, setGlobalSearchResults] = useState<BackendGlobalSearchResult[]>([])
  const [globalSearchLoading, setGlobalSearchLoading] = useState(false)
  const [globalSearchError, setGlobalSearchError] = useState('')
  const [attachmentDraft, setAttachmentDraft] = useState<AttachmentDraft | null>(null)
  const [mergeTicketBusy, setMergeTicketBusy] = useState('')
  const [caseLinkBusy, setCaseLinkBusy] = useState('')
  const [dashboardRange, setDashboardRange] = useState<DashboardRange>('all')
  const [dashboardTicketGroup, setDashboardTicketGroup] = useState('all')
  const [dashboardChatGroup, setDashboardChatGroup] = useState('all')
  const [dashboardAnalytics, setDashboardAnalytics] = useState<BackendAnalyticsSummary | null>(null)
  const [dashboardAnalyticsError, setDashboardAnalyticsError] = useState('')
  const [todos, setTodos] = useState<DashboardTodo[]>(() =>
    loadDashboardTodos(backendSession?.user.id ?? 'local'),
  )
  const [todoDraft, setTodoDraft] = useState('')
  const [watchedTicketIds, setWatchedTicketIds] = useState<string[]>(() =>
    loadWatchedTickets(backendSession?.user.id ?? 'local'),
  )
  const [timeLogs, setTimeLogs] = useState<Record<string, TicketTimeLog[]>>(() => loadTimeLogs())
  const [timeLogDraft, setTimeLogDraft] = useState('')
  const [inboxView, setInboxView] = useState('all-open')
  const [inboxSort, setInboxSort] = useState<'created' | 'updated' | 'priority'>('created')
  const [inboxLayout, setInboxLayout] = useState<'card' | 'table'>('card')
  const [ticketDetailOpen, setTicketDetailOpen] = useState(false)
  const [inboxPage, setInboxPage] = useState(0)
  const [inboxFiltersOpen, setInboxFiltersOpen] = useState(true)
  const [inboxGroup, setInboxGroup] = useState('all')
  const [inboxCreated, setInboxCreated] = useState<'all' | 'today' | 'week' | 'last-30'>('all')
  const [inboxDue, setInboxDue] = useState<'any' | 'today' | 'overdue'>('any')
  const [selectedTicketIds, setSelectedTicketIds] = useState<string[]>([])
  const [ticketDetailTab, setTicketDetailTab] = useState<TicketDetailTab>('activities')

  // Reset ticket-list pagination to the first page when filters/sort change.
  // (React's "adjust state during render" pattern — no effect, no cascading renders.)
  const inboxFilterKey = `${state.filters.search}|${state.filters.assignee}|${state.filters.status}|${state.filters.priority}|${state.filters.channel}|${state.filters.sentiment}|${state.filters.sla}|${inboxGroup}|${inboxCreated}|${inboxDue}|${inboxSort}`
  const [prevInboxFilterKey, setPrevInboxFilterKey] = useState(inboxFilterKey)
  if (inboxFilterKey !== prevInboxFilterKey) {
    setPrevInboxFilterKey(inboxFilterKey)
    setInboxPage(0)
  }
  const [channelConsoleView, setChannelConsoleView] = useState<ChannelConsoleView>('inbox')
  const [analyticsReportGroup, setAnalyticsReportGroup] = useState<AnalyticsReportGroup>('catalog')
  const [reportDraft, setReportDraft] = useState({ name: '', reportType: 'tickets' })
  const [reportBusy, setReportBusy] = useState(false)
  const [appointmentDraft, setAppointmentDraft] = useState({
    title: '',
    customerId: '',
    technicianId: '',
    scheduledAt: '',
    durationMinutes: 60,
    location: '',
    notes: '',
  })
  const [appointmentBusy, setAppointmentBusy] = useState(false)
  const [articleFormOpen, setArticleFormOpen] = useState(false)
  const [articleDraft, setArticleDraft] = useState({
    title: '',
    category: '',
    status: 'draft' as KnowledgeArticle['status'],
    language: 'en',
    body: '',
  })
  const [articleBusy, setArticleBusy] = useState(false)
  const [forumDraft, setForumDraft] = useState({ title: '', category: '', body: '' })
  const [forumBusy, setForumBusy] = useState(false)
  const [forumOpen, setForumOpen] = useState(false)
  const [expandedTopicId, setExpandedTopicId] = useState('')
  const [topicComments, setTopicComments] = useState<BackendDiscussionComment[]>([])
  const [topicCommentsBusy, setTopicCommentsBusy] = useState(false)
  const [commentDraft, setCommentDraft] = useState('')
  const [customerFormOpen, setCustomerFormOpen] = useState(false)
  const [customerDraft, setCustomerDraft] = useState({
    name: '',
    email: '',
    companyId: '',
    location: '',
    tags: '',
    notes: '',
  })
  const [customerBusy, setCustomerBusy] = useState(false)
  const [customerEditOpen, setCustomerEditOpen] = useState(false)
  const [customerEdit, setCustomerEdit] = useState({
    name: '',
    email: '',
    location: '',
    sentiment: 'neutral' as BackendCustomer['sentiment'],
    tags: '',
    notes: '',
  })
  const [loginEmail, setLoginEmail] = useState('gbolahan@omniticket.example.com')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginMfaCode, setLoginMfaCode] = useState('')
  const [loginMarket, setLoginMarket] = useState('market-ng')
  const oidcCallbackHandledRef = useRef(false)
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
    temporaryPassword: '',
    role: 'agent' as (typeof userRoleOptions)[number],
    permissionProfile: 'role_default' as BackendPermissionProfile,
    marketIds: ['market-ng'],
    defaultMarketId: 'market-ng',
  })
  const [supportGroupDraft, setSupportGroupDraft] = useState({
    name: '',
    description: '',
    teamEmail: '',
    skills: '',
    channels: [] as ChannelId[],
  })
  const [slaPolicyDraft, setSlaPolicyDraft] = useState({
    name: '',
    priority: 'medium' as Priority,
    firstResponseMinutes: 60,
    resolutionMinutes: 1440,
    businessHours: 'Business hours',
    channels: [] as ChannelId[],
    active: true,
    position: 40,
  })
  const [setupSection, setSetupSection] = useState<SetupSectionId>('people')
  const [setupModuleHint, setSetupModuleHint] = useState('')
  const [activeSetupTool, setActiveSetupTool] = useState<string | null>(null)
  const [peopleView, setPeopleView] = useState<'users' | 'groups' | 'security' | 'hours'>('users')
  const [businessHoursName, setBusinessHoursName] = useState('')
  const [businessHoursTimezone, setBusinessHoursTimezone] = useState('Africa/Lagos')
  const [businessHoursDrafts, setBusinessHoursDrafts] = useState<Record<string, BusinessHoursDay[]>>({})
  const [cannedDraft, setCannedDraft] = useState({ name: '', shortcut: '', body: '' })
  const [cannedEditId, setCannedEditId] = useState('')
  const [cannedEditDraft, setCannedEditDraft] = useState({ name: '', shortcut: '', body: '' })
  const [cannedBusy, setCannedBusy] = useState(false)
  const [templateDraft, setTemplateDraft] = useState<{
    name: string
    subject: string
    description: string
    priority: Priority
    group: string
    tags: string
  }>({ name: '', subject: '', description: '', priority: 'medium', group: '', tags: '' })
  const [templateBusy, setTemplateBusy] = useState(false)
  const [tagDraft, setTagDraft] = useState({ name: '', color: '#2f6fed', description: '' })
  const [tagBusy, setTagBusy] = useState(false)
  const [surveyDraft, setSurveyDraft] = useState({ name: '', question: '', scale: 5 })
  const [surveyBusy, setSurveyBusy] = useState(false)
  const [notifDraft, setNotifDraft] = useState({
    name: '',
    event: 'ticket_created',
    recipients: '',
    subject: '',
    body: '',
  })
  const [notifBusy, setNotifBusy] = useState(false)
  const [scenarioDraft, setScenarioDraft] = useState({ name: '', description: '' })
  const [scenarioActions, setScenarioActions] = useState<ScenarioAction[]>([])
  const [scenarioActionDraft, setScenarioActionDraft] = useState<ScenarioAction>({
    type: 'add_tag',
    value: '',
  })
  const [scenarioBusy, setScenarioBusy] = useState(false)
  const [customFieldEntity, setCustomFieldEntity] = useState<'contact' | 'company'>('contact')
  const [customFieldDraft, setCustomFieldDraft] = useState<{
    key: string
    label: string
    fieldType: TicketFieldType
    required: boolean
    options: string
  }>({ key: '', label: '', fieldType: 'text', required: false, options: '' })
  const [customFieldBusy, setCustomFieldBusy] = useState(false)
  const [objectDraft, setObjectDraft] = useState({ key: '', name: '', description: '' })
  const [objectFields, setObjectFields] = useState<CustomObjectField[]>([])
  const [objectFieldDraft, setObjectFieldDraft] = useState<{ key: string; label: string; fieldType: TicketFieldType }>(
    { key: '', label: '', fieldType: 'text' },
  )
  const [objectBusy, setObjectBusy] = useState(false)
  const [productDraft, setProductDraft] = useState({ name: '', code: '', description: '' })
  const [productBusy, setProductBusy] = useState(false)
  const [addUserOpen, setAddUserOpen] = useState(false)
  const [addGroupOpen, setAddGroupOpen] = useState(false)
  const [addSlaPolicyOpen, setAddSlaPolicyOpen] = useState(false)
  const [emailSettingsDraft, setEmailSettingsDraft] =
    useState<EmailSettingsDraft>(defaultEmailSettingsDraft)
  const [emailSettingsBusy, setEmailSettingsBusy] = useState(false)
  const [integrationCredentialDraft, setIntegrationCredentialDraft] =
    useState<IntegrationCredentialDraft>(defaultIntegrationCredentialDraft)
  const [integrationCredentialBusy, setIntegrationCredentialBusy] = useState(false)
  const [ssoSettingsDraft, setSsoSettingsDraft] = useState({
    enabled: false,
    providerName: 'Enterprise SSO',
    issuerUrl: '',
    authorizationUrl: '',
    tokenUrl: '',
    userinfoUrl: '',
    clientId: '',
    clientSecret: '',
    clearClientSecret: false,
    redirectUrl: '',
    allowedEmailDomains: '',
    autoProvisionEnabled: false,
    defaultRole: 'agent' as BackendSsoProviderSettings['default_role'],
    defaultMarketId: '',
    requireEmailVerified: true,
  })
  const [ssoSettingsBusy, setSsoSettingsBusy] = useState(false)
  const [brandingDraft, setBrandingDraft] = useState({
    publicBrandName: 'Omni Ticket',
    portalSupportName: '',
    portalPrimaryColor: '#0b5eea',
    portalLogoUrl: '',
    portalWelcomeMessage: '',
  })
  const [brandingBusy, setBrandingBusy] = useState(false)
  const [widgetDraft, setWidgetDraft] = useState({
    enabled: false,
    displayName: 'Chat with us',
    welcomeMessage: '',
    primaryColor: '#0b5eea',
    launcherLabel: 'Support',
    position: 'bottom-right',
    autoOpenSeconds: 0,
    collectEmail: true,
    offlineMessage: '',
  })
  const [widgetBusy, setWidgetBusy] = useState(false)
  const [productionAccountPack, setProductionAccountPack] =
    useState<BackendProductionAccountRequestPack | null>(null)
  const [productionAccountBusy, setProductionAccountBusy] = useState(false)
  const [productionAccountDelivery, setProductionAccountDelivery] =
    useState<BackendProductionAccountRequestDelivery | null>(null)
  const [productionAccountSendBusy, setProductionAccountSendBusy] = useState(false)
  const [productionAccountReferences, setProductionAccountReferences] =
    useState<BackendProductionAccountReference[]>([])
  const [productionAccountReferenceDocs, setProductionAccountReferenceDocs] =
    useState<BackendProductionAccountReferenceDocs | null>(null)
  const [productionAccountReferenceBusy, setProductionAccountReferenceBusy] = useState(false)
  const [productionAccountReferenceDraft, setProductionAccountReferenceDraft] = useState({
    provider: 'email',
    area: 'Email inbound/outbound',
    accountName: '',
    accountIdentifier: '',
    status: 'requested' as BackendProductionAccountReferenceStatus,
    ownerEmail: '',
    credentialReference: '',
    docsReference: 'API_DOCS.md#external-accounts-needed',
    callbackUrls: '',
    notes: '',
  })
  const [productionReadinessChecklist, setProductionReadinessChecklist] =
    useState<BackendProductionReadinessChecklist | null>(null)
  const [productionReadinessBusy, setProductionReadinessBusy] = useState(false)
  const [userSearch, setUserSearch] = useState('')
  const [ticketFieldDraft, setTicketFieldDraft] = useState({
    label: '',
    key: '',
    fieldType: 'text' as TicketFieldType,
    options: '',
    channels: [] as ChannelId[],
    required: false,
    active: true,
    position: 100,
  })
  const [userActionBusy, setUserActionBusy] = useState(false)
  const [groupActionBusy, setGroupActionBusy] = useState(false)
  const [slaPolicyActionBusy, setSlaPolicyActionBusy] = useState(false)
  const [passwordChange, setPasswordChange] = useState({
    currentPassword: '',
    newPassword: '',
  })
  const [mfaEnrollment, setMfaEnrollment] = useState<BackendMfaEnrollment | null>(null)
  const [mfaConfirmCode, setMfaConfirmCode] = useState('')
  const [mfaDisable, setMfaDisable] = useState({
    currentPassword: '',
    code: '',
  })
  const [passwordResetDrafts, setPasswordResetDrafts] = useState<Record<string, string>>({})
  const [auditRetention, setAuditRetention] = useState<BackendAuditRetentionPolicy | null>(null)
  const [attachmentRetention, setAttachmentRetention] = useState<BackendAttachmentRetentionPolicy | null>(null)
  const [auditActionBusy, setAuditActionBusy] = useState(false)
  const [attachmentActionBusy, setAttachmentActionBusy] = useState(false)
  const [portalMarket, setPortalMarket] = useState('ng')
  const [portalQuery, setPortalQuery] = useState('')
  const [portalAnswers, setPortalAnswers] = useState<BackendPortalAnswerSuggestion[]>([])
  const [portalTicketFields, setPortalTicketFields] = useState<BackendTicketField[]>([])
  const [portalLoading, setPortalLoading] = useState(false)
  const [portalSubmitting, setPortalSubmitting] = useState(false)
  const [portalNotice, setPortalNotice] = useState('')
  const [portalSearchError, setPortalSearchError] = useState('')
  const [portalDraft, setPortalDraft] = useState({
    name: '',
    email: '',
    phone: '',
    subject: '',
    description: '',
    priority: 'normal' as NonNullable<BackendCreatePortalTicketInput['priority']>,
    customFields: {} as Record<string, unknown>,
  })
  const [portalLookup, setPortalLookup] = useState({
    publicId: '',
    email: '',
  })
  const [portalTicketDetail, setPortalTicketDetail] = useState<BackendPortalTicketDetail | null>(null)
  const [portalLookupBusy, setPortalLookupBusy] = useState(false)
  const [portalReplyBusy, setPortalReplyBusy] = useState(false)
  const [portalReplyBody, setPortalReplyBody] = useState('')
  const [portalAttachmentFile, setPortalAttachmentFile] = useState<File | null>(null)
  const [portalReplyAttachmentFile, setPortalReplyAttachmentFile] = useState<File | null>(null)
  const [portalLookupNotice, setPortalLookupNotice] = useState('')

  const selectedAgent = state.agents.find((agent) => agent.id === selectedConversation.assigneeId)
  const selectedChannel =
    state.channels.find((channel) => channel.id === selectedConversation.channelId) ?? state.channels[0]
  const receivingGroup = state.supportGroups.find((group) => group.name === selectedConversation.group)
  const focusedChannel =
    state.channels.find((channel) => channel.id === state.selectedChannelId) ?? undefined

  const composerMacroOptions = useMemo<ResponseMacroSuggestion[]>(() => {
    const suggested = selectedConversation.copilot.responseMacros ?? []
    const suggestedIds = new Set(suggested.map((item) => item.macro.id))
    const catalog = state.responseMacros
      .filter(
        (macro) =>
          macro.active &&
          !suggestedIds.has(macro.id) &&
          (macro.channels.length === 0 || macro.channels.includes(composerChannel)),
      )
      .sort((a, b) => b.usageCount - a.usageCount || a.name.localeCompare(b.name))
      .map((macro) => ({
        macro,
        score: 0,
        reasons: macro.shortcut ? [macro.shortcut] : [],
        matchedTerms: macro.tags,
      }))
    return [...suggested, ...catalog]
  }, [composerChannel, selectedConversation.copilot.responseMacros, state.responseMacros])

  const activeSupportGroups = useMemo(
    () => state.supportGroups.filter((group) => group.active),
    [state.supportGroups],
  )
  const handoffTeamOptions = useMemo(
    () => (activeSupportGroups.length ? activeSupportGroups.map((group) => group.name) : handoffTeams),
    [activeSupportGroups],
  )
  const effectiveHandoffTeam = handoffTeamOptions.includes(handoffTeam)
    ? handoffTeam
    : handoffTeamOptions[0] ?? handoffTeams[0]

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
  const oidcProviderConfig = backendSync.oidcProviderConfig
  const currentMarket = backendSession?.market
  const emailProviderSettings: BackendEmailProviderSettings | null =
    backendSnapshot?.emailProviderSettings ?? backendSnapshot?.email_provider_settings ?? null
  const integrationCredentialSettings: BackendIntegrationCredentialSettings | null =
    backendSnapshot?.integrationCredentialSettings ?? backendSnapshot?.integration_credential_settings ?? null
  const ssoProviderSettings: BackendSsoProviderSettings | null =
    backendSnapshot?.ssoProviderSettings ?? backendSnapshot?.sso_provider_settings ?? null
  const workspaceSettings = backendSnapshot?.settings ?? null
  const widgetSettings: BackendWidgetSettings | null =
    backendSnapshot?.widgetSettings ?? backendSnapshot?.widget_settings ?? null
  const availableMarkets = backendSession?.available_markets ?? []
  const operationalAlerts = backendSnapshot?.operationalAlerts ?? backendSnapshot?.operational_alerts ?? []
  const alertDeliveries = backendSnapshot?.alertDeliveries ?? backendSnapshot?.alert_deliveries ?? []
  const alertDeliveryConfig =
    backendSnapshot?.alertDeliveryConfig ?? backendSnapshot?.alert_delivery_config
  const outboundProviderConfig =
    backendSnapshot?.outboundProviderConfig ?? backendSnapshot?.outbound_provider_config ?? []
  const attachmentProviderConfig: BackendAttachmentProviderConfig | null =
    backendSnapshot?.attachmentProviderConfig ?? backendSnapshot?.attachment_provider_config ?? null
  const productionAccountActionItems =
    productionAccountPack?.items.filter((item) => item.status !== 'ready') ?? []
  const activeOperationalAlerts = operationalAlerts.filter((alert) => alert.status !== 'resolved')
  const operationalAlertHref = `${routeHref({ screen: 'admin' }).split('#')[0]}#operational-alerts`

  const activeDirectChannelId = isDirectMessageChannel(state.selectedChannelId)
    ? state.selectedChannelId
    : 'whatsapp'
  const isPortalRoute =
    state.selectedScreen === 'portal' ||
    (typeof window !== 'undefined' &&
      new URLSearchParams(window.location.search).get('screen') === 'portal')

  // Personal dashboard to-dos persist per user in localStorage (personal scratch,
  // not shared content). Reload when the signed-in user changes; persist on edit.
  const todoUserId = backendSession?.user.id ?? 'local'
  const previousTodoUser = useRef(todoUserId)
  useEffect(() => {
    if (previousTodoUser.current === todoUserId) return
    previousTodoUser.current = todoUserId
    setTodos(loadDashboardTodos(todoUserId))
    setWatchedTicketIds(loadWatchedTickets(todoUserId))
  }, [todoUserId])
  useEffect(() => {
    saveDashboardTodos(todoUserId, todos)
  }, [todoUserId, todos])
  useEffect(() => {
    saveWatchedTickets(todoUserId, watchedTicketIds)
  }, [todoUserId, watchedTicketIds])
  useEffect(() => {
    if (!backendSession || !online) {
      return
    }
    const controller = new AbortController()
    fetchBackendAnalyticsSummary(
      backendSession,
      {
        range: dashboardRange,
        ticket_group: dashboardTicketGroup,
        chat_group: dashboardChatGroup,
      },
      controller.signal,
    )
      .then((analytics) => {
        setDashboardAnalytics(analytics)
        setDashboardAnalyticsError('')
      })
      .catch((error) => {
        if (controller.signal.aborted) return
        setDashboardAnalytics(null)
        setDashboardAnalyticsError(error instanceof Error ? error.message : 'Dashboard metrics failed to load')
      })
    return () => controller.abort()
  }, [
    backendSession,
    backendSync.lastSyncAt,
    dashboardChatGroup,
    dashboardRange,
    dashboardTicketGroup,
    online,
  ])
  useEffect(() => {
    saveTimeLogs(timeLogs)
  }, [timeLogs])

  // Keyboard shortcuts for the open ticket (the action bar advertises these via <kbd>).
  // A ref always points at the latest handler so the listener stays subscribed once.
  const ticketActionRef = useRef(handleTicketAction)
  useEffect(() => {
    ticketActionRef.current = handleTicketAction
  })
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (state.selectedScreen !== 'inbox') return
      // Ignore modifier combos and bare modifier/navigation keys (Shift, Tab, arrows…)
      // so that holding Shift never triggers an action. Only plain single-character keys map.
      if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return
      if (event.key.length !== 1) return
      const target = event.target as HTMLElement | null
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)
      ) {
        return
      }
      const key = event.key.toLowerCase()
      if (key === 'j' || key === 'k') {
        event.preventDefault()
        setGlobalSearchOpen(true)
        return
      }
      const action = freshdeskTicketActionItems.find((item) => item.shortcut && item.shortcut === key)
      if (action) {
        event.preventDefault()
        ticketActionRef.current(action.id)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [state.selectedScreen])

  useEffect(() => {
    const syncDraft = () => {
      if (!emailProviderSettings) {
        setEmailSettingsDraft((current) => ({
          ...current,
          inboundUsername: current.inboundUsername || currentMarket?.support_email || '',
          outboundUsername: current.outboundUsername || currentMarket?.support_email || '',
          outboundFromEmail: current.outboundFromEmail || currentMarket?.support_email || '',
        }))
        return
      }
      setEmailSettingsDraft({
        inboundEnabled: emailProviderSettings.inbound_enabled,
        inboundHost: emailProviderSettings.inbound_host,
        inboundPort: emailProviderSettings.inbound_port,
        inboundUsername: emailProviderSettings.inbound_username || currentMarket?.support_email || '',
        inboundPassword: '',
        inboundMailbox: emailProviderSettings.inbound_mailbox || 'INBOX',
        inboundUseSsl: emailProviderSettings.inbound_use_ssl,
        inboundMarkSeen: emailProviderSettings.inbound_mark_seen,
        clearInboundPassword: false,
        outboundEnabled: emailProviderSettings.outbound_enabled,
        outboundHost: emailProviderSettings.outbound_host,
        outboundPort: emailProviderSettings.outbound_port,
        outboundUsername: emailProviderSettings.outbound_username || currentMarket?.support_email || '',
        outboundPassword: '',
        outboundFromEmail: emailProviderSettings.outbound_from_email || currentMarket?.support_email || '',
        outboundUseStarttls: emailProviderSettings.outbound_use_starttls,
        outboundUseSsl: emailProviderSettings.outbound_use_ssl,
        clearOutboundPassword: false,
      })
    }
    const timeoutId = window.setTimeout(syncDraft, 0)
    return () => window.clearTimeout(timeoutId)
  }, [currentMarket?.support_email, emailProviderSettings])

  useEffect(() => {
    const syncDraft = () => {
      if (!integrationCredentialSettings) return
      setIntegrationCredentialDraft({
        aiProvider: integrationCredentialSettings.ai_provider,
        anthropicApiKey: '',
        anthropicApiBaseUrl: integrationCredentialSettings.anthropic_api_base_url,
        anthropicModel: integrationCredentialSettings.anthropic_model,
        clearAnthropicApiKey: false,
        alertWebhookUrl: integrationCredentialSettings.alert_webhook_url,
        alertWebhookSecret: '',
        alertDeliveryMinSeverity: integrationCredentialSettings.alert_delivery_min_severity,
        clearAlertWebhookSecret: false,
        smsHttpEndpoint: integrationCredentialSettings.sms_http_endpoint,
        smsHttpAuthToken: '',
        smsHttpFrom: integrationCredentialSettings.sms_http_from,
        smsHttpAuthHeader: integrationCredentialSettings.sms_http_auth_header,
        smsHttpAuthScheme: integrationCredentialSettings.sms_http_auth_scheme,
        smsHttpDeliveryCallbackUrl: integrationCredentialSettings.sms_http_delivery_callback_url,
        clearSmsHttpAuthToken: false,
        voiceHttpEndpoint: integrationCredentialSettings.voice_http_endpoint,
        voiceHttpAuthToken: '',
        voiceHttpFrom: integrationCredentialSettings.voice_http_from,
        voiceHttpAuthHeader: integrationCredentialSettings.voice_http_auth_header,
        voiceHttpAuthScheme: integrationCredentialSettings.voice_http_auth_scheme,
        voiceHttpStatusCallbackUrl: integrationCredentialSettings.voice_http_status_callback_url,
        clearVoiceHttpAuthToken: false,
        whatsappCloudApiBaseUrl: integrationCredentialSettings.whatsapp_cloud_api_base_url,
        whatsappPhoneNumberId: integrationCredentialSettings.whatsapp_phone_number_id,
        whatsappAccessToken: '',
        whatsappPreviewUrls: integrationCredentialSettings.whatsapp_preview_urls,
        clearWhatsappAccessToken: false,
        facebookGraphApiBaseUrl: integrationCredentialSettings.facebook_graph_api_base_url,
        facebookPageId: integrationCredentialSettings.facebook_page_id,
        facebookPageAccessToken: '',
        facebookMessagingType: integrationCredentialSettings.facebook_messaging_type,
        clearFacebookPageAccessToken: false,
        instagramGraphApiBaseUrl: integrationCredentialSettings.instagram_graph_api_base_url,
        instagramBusinessAccountId: integrationCredentialSettings.instagram_business_account_id,
        instagramAccessToken: '',
        clearInstagramAccessToken: false,
      })
    }
    const timeoutId = window.setTimeout(syncDraft, 0)
    return () => window.clearTimeout(timeoutId)
  }, [integrationCredentialSettings])

  useEffect(() => {
    function syncDraft() {
      if (!ssoProviderSettings) return
      setSsoSettingsDraft({
        enabled: ssoProviderSettings.enabled,
        providerName: ssoProviderSettings.provider_name,
        issuerUrl: ssoProviderSettings.issuer_url,
        authorizationUrl: ssoProviderSettings.authorization_url,
        tokenUrl: ssoProviderSettings.token_url,
        userinfoUrl: ssoProviderSettings.userinfo_url,
        clientId: ssoProviderSettings.client_id,
        clientSecret: '',
        clearClientSecret: false,
        redirectUrl: ssoProviderSettings.redirect_url,
        allowedEmailDomains: ssoProviderSettings.allowed_email_domains.join(', '),
        autoProvisionEnabled: ssoProviderSettings.auto_provision_enabled,
        defaultRole: ssoProviderSettings.default_role,
        defaultMarketId: ssoProviderSettings.default_market_id ?? '',
        requireEmailVerified: ssoProviderSettings.require_email_verified,
      })
    }
    const timeoutId = window.setTimeout(syncDraft, 0)
    return () => window.clearTimeout(timeoutId)
  }, [ssoProviderSettings])

  useEffect(() => {
    function syncDraft() {
      if (!workspaceSettings) return
      setBrandingDraft({
        publicBrandName: workspaceSettings.public_brand_name ?? 'Omni Ticket',
        portalSupportName: workspaceSettings.portal_support_name ?? '',
        portalPrimaryColor: workspaceSettings.portal_primary_color || '#0b5eea',
        portalLogoUrl: workspaceSettings.portal_logo_url ?? '',
        portalWelcomeMessage: workspaceSettings.portal_welcome_message ?? '',
      })
    }
    const timeoutId = window.setTimeout(syncDraft, 0)
    return () => window.clearTimeout(timeoutId)
  }, [workspaceSettings])

  useEffect(() => {
    function syncDraft() {
      if (!widgetSettings) return
      setWidgetDraft({
        enabled: widgetSettings.enabled,
        displayName: widgetSettings.display_name,
        welcomeMessage: widgetSettings.welcome_message,
        primaryColor: widgetSettings.primary_color || '#0b5eea',
        launcherLabel: widgetSettings.launcher_label,
        position: widgetSettings.position || 'bottom-right',
        autoOpenSeconds: widgetSettings.auto_open_seconds,
        collectEmail: widgetSettings.collect_email,
        offlineMessage: widgetSettings.offline_message,
      })
    }
    const timeoutId = window.setTimeout(syncDraft, 0)
    return () => window.clearTimeout(timeoutId)
  }, [widgetSettings])

  const operationalNotifications = activeOperationalAlerts.slice(0, 3).map((alert) => ({
    id: alert.id,
    title: alert.title,
    body: alert.message,
    action: () => selectScreen('admin'),
    href: operationalAlertHref,
  }))
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
    ...operationalNotifications,
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

  useEffect(() => {
    if (!isPortalRoute) return undefined
    let cancelled = false
    const query = portalQuery.trim()
    const timer = window.setTimeout(() => {
      setPortalLoading(true)
      fetchBackendPortalAnswers(portalMarket, query, 5)
        .then((response) => {
          if (cancelled) return
          setPortalAnswers(response.suggestions)
          setPortalTicketFields(response.ticket_fields)
          setPortalSearchError('')
        })
        .catch((error) => {
          if (cancelled) return
          setPortalAnswers([])
          setPortalTicketFields([])
          setPortalSearchError(error instanceof Error ? error.message : 'Help Center is unavailable.')
        })
        .finally(() => {
          if (!cancelled) setPortalLoading(false)
        })
    }, query ? 240 : 0)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [isPortalRoute, portalMarket, portalQuery])

  useEffect(() => {
    if (backendSession || oidcCallbackHandledRef.current) return
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const stateValue = params.get('state')
    if (!code || !stateValue) return
    oidcCallbackHandledRef.current = true
    completeOidcLogin({ code, state: stateValue }).then((success) => {
      if (!success) return
      const nextParams = new URLSearchParams(window.location.search)
      nextParams.delete('auth')
      nextParams.delete('code')
      nextParams.delete('state')
      nextParams.delete('error')
      nextParams.set('screen', 'command')
      window.history.replaceState(null, '', `${window.location.pathname}?${nextParams.toString()}`)
    })
  }, [backendSession, completeOidcLogin])

  useEffect(() => {
    let cancelled = false
    if (!backendSession) {
      return undefined
    }

    fetchBackendAuditRetentionPolicy(backendSession)
      .then((policy) => {
        if (!cancelled) setAuditRetention(policy)
      })
      .catch(() => {
        if (!cancelled) setAuditRetention(null)
      })

    return () => {
      cancelled = true
    }
  }, [backendSession, backendSync.lastSyncAt])

  useEffect(() => {
    let cancelled = false
    if (!backendSession || setupSection !== 'connectors') {
      return undefined
    }

    fetchBackendProductionAccountRequests(backendSession)
      .then((pack) => {
        if (!cancelled) setProductionAccountPack(pack)
      })
      .catch(() => {
        if (!cancelled) setProductionAccountPack(null)
      })

    return () => {
      cancelled = true
    }
  }, [backendSession, backendSync.lastSyncAt, setupSection])

  useEffect(() => {
    let cancelled = false
    if (!backendSession || setupSection !== 'connectors') {
      return undefined
    }

    fetchBackendProductionReadinessChecklist(backendSession)
      .then((checklist) => {
        if (!cancelled) setProductionReadinessChecklist(checklist)
      })
      .catch(() => {
        if (!cancelled) setProductionReadinessChecklist(null)
      })

    return () => {
      cancelled = true
    }
  }, [backendSession, backendSync.lastSyncAt, setupSection])

  useEffect(() => {
    let cancelled = false
    if (!backendSession || setupSection !== 'connectors') {
      return undefined
    }

    Promise.all([
      fetchBackendProductionAccountReferences(backendSession),
      fetchBackendProductionAccountReferenceDocs(backendSession),
    ])
      .then(([references, docs]) => {
        if (!cancelled) {
          setProductionAccountReferences(references)
          setProductionAccountReferenceDocs(docs)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProductionAccountReferences([])
          setProductionAccountReferenceDocs(null)
        }
      })

    return () => {
      cancelled = true
    }
  }, [backendSession, backendSync.lastSyncAt, setupSection])

  useEffect(() => {
    let cancelled = false
    if (!backendSession) {
      return undefined
    }

    fetchBackendAttachmentRetentionPolicy(backendSession)
      .then((policy) => {
        if (!cancelled) setAttachmentRetention(policy)
      })
      .catch(() => {
        if (!cancelled) setAttachmentRetention(null)
      })

    return () => {
      cancelled = true
    }
  }, [backendSession, backendSync.lastSyncAt])

  useEffect(() => {
    const query = state.filters.search.trim()
    if (!backendSession || query.length < 2) {
      return undefined
    }

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setGlobalSearchLoading(true)
      setGlobalSearchError('')
      fetchBackendGlobalSearch(query, backendSession, 10, controller.signal)
        .then((results) => {
          setGlobalSearchResults(results)
        })
        .catch((error) => {
          if (controller.signal.aborted) return
          setGlobalSearchResults([])
          setGlobalSearchError(error instanceof Error ? error.message : 'Search is unavailable.')
        })
        .finally(() => {
          if (!controller.signal.aborted) setGlobalSearchLoading(false)
        })
    }, 220)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [backendSession, state.filters.search])

  function downloadAuditExport(content: string, contentType: string, filename: string) {
    const blob = new Blob([content], { type: contentType })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    window.URL.revokeObjectURL(url)
  }

  async function handleAuditExport(format: BackendAuditExportFormat) {
    if (!backendSession || auditActionBusy) return
    setAuditActionBusy(true)
    try {
      const exportPayload = await exportBackendAudit(
        {
          format,
          limit: auditRetention?.export_max_rows ?? 1000,
        },
        backendSession,
      )
      downloadAuditExport(exportPayload.content, exportPayload.contentType, exportPayload.filename)
      setPrototypeNotice(`Audit ${format.toUpperCase()} export downloaded.`)
      const policy = await fetchBackendAuditRetentionPolicy(backendSession)
      setAuditRetention(policy)
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Audit export failed.')
    } finally {
      setAuditActionBusy(false)
    }
  }

  async function handleAuditPrune() {
    if (!backendSession || auditActionBusy) return
    setAuditActionBusy(true)
    try {
      const result = await pruneBackendAuditRetention(backendSession)
      setAuditRetention(result.policy)
      setPrototypeNotice(`${result.deleted_events} audit event(s) pruned by retention policy.`)
      await refreshBackend()
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Audit retention prune failed.')
    } finally {
      setAuditActionBusy(false)
    }
  }

  async function handleAttachmentPrune() {
    if (!backendSession || attachmentActionBusy) return
    setAttachmentActionBusy(true)
    try {
      const result = await pruneBackendAttachmentRetention(backendSession)
      setAttachmentRetention(result.policy)
      setPrototypeNotice(`${result.purged_attachments} attachment(s) purged by retention policy.`)
      await refreshBackend()
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Attachment retention prune failed.')
    } finally {
      setAttachmentActionBusy(false)
    }
  }

  async function handleEmailSettingsSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!backendSession || emailSettingsBusy) return
    if (emailSettingsDraft.outboundUseSsl && emailSettingsDraft.outboundUseStarttls) {
      setPrototypeNotice('SMTP can use SSL or STARTTLS, not both.')
      return
    }
    setEmailSettingsBusy(true)
    try {
      const patch: BackendUpdateEmailProviderSettingsInput = {
        inbound_enabled: emailSettingsDraft.inboundEnabled,
        inbound_host: emailSettingsDraft.inboundHost.trim(),
        inbound_port: Number(emailSettingsDraft.inboundPort || 993),
        inbound_username: emailSettingsDraft.inboundUsername.trim(),
        inbound_mailbox: emailSettingsDraft.inboundMailbox.trim() || 'INBOX',
        inbound_use_ssl: emailSettingsDraft.inboundUseSsl,
        inbound_mark_seen: emailSettingsDraft.inboundMarkSeen,
        clear_inbound_password: emailSettingsDraft.clearInboundPassword,
        outbound_enabled: emailSettingsDraft.outboundEnabled,
        outbound_host: emailSettingsDraft.outboundHost.trim(),
        outbound_port: Number(emailSettingsDraft.outboundPort || 587),
        outbound_username: emailSettingsDraft.outboundUsername.trim(),
        outbound_from_email: emailSettingsDraft.outboundFromEmail.trim(),
        outbound_use_starttls: emailSettingsDraft.outboundUseStarttls,
        outbound_use_ssl: emailSettingsDraft.outboundUseSsl,
        clear_outbound_password: emailSettingsDraft.clearOutboundPassword,
      }
      if (emailSettingsDraft.inboundPassword.trim()) {
        patch.inbound_password = emailSettingsDraft.inboundPassword.trim()
      }
      if (emailSettingsDraft.outboundPassword.trim()) {
        patch.outbound_password = emailSettingsDraft.outboundPassword.trim()
      }
      const updated = await patchBackendEmailSettings(patch, backendSession)
      setEmailSettingsDraft({
        inboundEnabled: updated.inbound_enabled,
        inboundHost: updated.inbound_host,
        inboundPort: updated.inbound_port,
        inboundUsername: updated.inbound_username || currentMarket?.support_email || '',
        inboundPassword: '',
        inboundMailbox: updated.inbound_mailbox || 'INBOX',
        inboundUseSsl: updated.inbound_use_ssl,
        inboundMarkSeen: updated.inbound_mark_seen,
        clearInboundPassword: false,
        outboundEnabled: updated.outbound_enabled,
        outboundHost: updated.outbound_host,
        outboundPort: updated.outbound_port,
        outboundUsername: updated.outbound_username || currentMarket?.support_email || '',
        outboundPassword: '',
        outboundFromEmail: updated.outbound_from_email || currentMarket?.support_email || '',
        outboundUseStarttls: updated.outbound_use_starttls,
        outboundUseSsl: updated.outbound_use_ssl,
        clearOutboundPassword: false,
      })
      setPrototypeNotice('Email setup saved.')
      await refreshBackend()
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Email setup save failed.')
    } finally {
      setEmailSettingsBusy(false)
    }
  }

  async function handleSsoSettingsSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!backendSession || ssoSettingsBusy) return
    setSsoSettingsBusy(true)
    try {
      const patch: BackendUpdateSsoProviderSettingsInput = {
        enabled: ssoSettingsDraft.enabled,
        provider_name: ssoSettingsDraft.providerName.trim() || 'Enterprise SSO',
        issuer_url: ssoSettingsDraft.issuerUrl.trim(),
        authorization_url: ssoSettingsDraft.authorizationUrl.trim(),
        token_url: ssoSettingsDraft.tokenUrl.trim(),
        userinfo_url: ssoSettingsDraft.userinfoUrl.trim(),
        client_id: ssoSettingsDraft.clientId.trim(),
        clear_client_secret: ssoSettingsDraft.clearClientSecret,
        redirect_url: ssoSettingsDraft.redirectUrl.trim(),
        allowed_email_domains: ssoSettingsDraft.allowedEmailDomains
          .split(',')
          .map((domain) => domain.trim())
          .filter((domain) => domain.length > 0),
        auto_provision_enabled: ssoSettingsDraft.autoProvisionEnabled,
        default_role: ssoSettingsDraft.defaultRole,
        default_market_id: ssoSettingsDraft.defaultMarketId.trim(),
        require_email_verified: ssoSettingsDraft.requireEmailVerified,
      }
      if (!ssoSettingsDraft.clearClientSecret && ssoSettingsDraft.clientSecret.trim()) {
        patch.client_secret = ssoSettingsDraft.clientSecret.trim()
      }
      await patchBackendSsoSettings(patch, backendSession)
      setPrototypeNotice('Enterprise SSO settings saved.')
      await refreshBackend()
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'SSO settings save failed.')
    } finally {
      setSsoSettingsBusy(false)
    }
  }

  async function handleBrandingSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!backendSession || brandingBusy) return
    setBrandingBusy(true)
    try {
      await patchBackendSettings(
        {
          public_brand_name: brandingDraft.publicBrandName.trim() || 'Omni Ticket',
          portal_support_name: brandingDraft.portalSupportName.trim(),
          portal_primary_color: brandingDraft.portalPrimaryColor.trim() || '#0b5eea',
          portal_logo_url: brandingDraft.portalLogoUrl.trim(),
          portal_welcome_message: brandingDraft.portalWelcomeMessage.trim(),
        },
        backendSession,
      )
      setPrototypeNotice('Portal branding saved.')
      await refreshBackend()
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Branding save failed.')
    } finally {
      setBrandingBusy(false)
    }
  }

  async function handleWidgetSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!backendSession || widgetBusy) return
    setWidgetBusy(true)
    try {
      await patchBackendWidgetSettings(
        {
          enabled: widgetDraft.enabled,
          display_name: widgetDraft.displayName.trim() || 'Chat with us',
          welcome_message: widgetDraft.welcomeMessage.trim(),
          primary_color: widgetDraft.primaryColor.trim() || '#0b5eea',
          launcher_label: widgetDraft.launcherLabel.trim() || 'Support',
          position: widgetDraft.position,
          auto_open_seconds: widgetDraft.autoOpenSeconds,
          collect_email: widgetDraft.collectEmail,
          offline_message: widgetDraft.offlineMessage.trim(),
        },
        backendSession,
      )
      setPrototypeNotice('Chat widget settings saved.')
      await refreshBackend()
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Widget save failed.')
    } finally {
      setWidgetBusy(false)
    }
  }

  async function handleIntegrationCredentialSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!backendSession || integrationCredentialBusy) return
    setIntegrationCredentialBusy(true)
    try {
      const patch: BackendUpdateIntegrationCredentialSettingsInput = {
        ai_provider: integrationCredentialDraft.aiProvider,
        anthropic_api_base_url: integrationCredentialDraft.anthropicApiBaseUrl.trim(),
        anthropic_model: integrationCredentialDraft.anthropicModel.trim(),
        clear_anthropic_api_key: integrationCredentialDraft.clearAnthropicApiKey,
        alert_webhook_url: integrationCredentialDraft.alertWebhookUrl.trim(),
        alert_delivery_min_severity: integrationCredentialDraft.alertDeliveryMinSeverity,
        clear_alert_webhook_secret: integrationCredentialDraft.clearAlertWebhookSecret,
        sms_http_endpoint: integrationCredentialDraft.smsHttpEndpoint.trim(),
        sms_http_from: integrationCredentialDraft.smsHttpFrom.trim(),
        sms_http_auth_header: integrationCredentialDraft.smsHttpAuthHeader.trim() || 'Authorization',
        sms_http_auth_scheme: integrationCredentialDraft.smsHttpAuthScheme.trim(),
        sms_http_delivery_callback_url: integrationCredentialDraft.smsHttpDeliveryCallbackUrl.trim(),
        clear_sms_http_auth_token: integrationCredentialDraft.clearSmsHttpAuthToken,
        voice_http_endpoint: integrationCredentialDraft.voiceHttpEndpoint.trim(),
        voice_http_from: integrationCredentialDraft.voiceHttpFrom.trim(),
        voice_http_auth_header: integrationCredentialDraft.voiceHttpAuthHeader.trim() || 'Authorization',
        voice_http_auth_scheme: integrationCredentialDraft.voiceHttpAuthScheme.trim(),
        voice_http_status_callback_url: integrationCredentialDraft.voiceHttpStatusCallbackUrl.trim(),
        clear_voice_http_auth_token: integrationCredentialDraft.clearVoiceHttpAuthToken,
        whatsapp_cloud_api_base_url: integrationCredentialDraft.whatsappCloudApiBaseUrl.trim(),
        whatsapp_phone_number_id: integrationCredentialDraft.whatsappPhoneNumberId.trim(),
        whatsapp_preview_urls: integrationCredentialDraft.whatsappPreviewUrls,
        clear_whatsapp_access_token: integrationCredentialDraft.clearWhatsappAccessToken,
        facebook_graph_api_base_url: integrationCredentialDraft.facebookGraphApiBaseUrl.trim(),
        facebook_page_id: integrationCredentialDraft.facebookPageId.trim(),
        facebook_messaging_type: integrationCredentialDraft.facebookMessagingType.trim() || 'RESPONSE',
        clear_facebook_page_access_token: integrationCredentialDraft.clearFacebookPageAccessToken,
        instagram_graph_api_base_url: integrationCredentialDraft.instagramGraphApiBaseUrl.trim(),
        instagram_business_account_id: integrationCredentialDraft.instagramBusinessAccountId.trim(),
        clear_instagram_access_token: integrationCredentialDraft.clearInstagramAccessToken,
      }
      if (integrationCredentialDraft.anthropicApiKey.trim()) {
        patch.anthropic_api_key = integrationCredentialDraft.anthropicApiKey.trim()
      }
      if (integrationCredentialDraft.alertWebhookSecret.trim()) {
        patch.alert_webhook_secret = integrationCredentialDraft.alertWebhookSecret.trim()
      }
      if (integrationCredentialDraft.smsHttpAuthToken.trim()) {
        patch.sms_http_auth_token = integrationCredentialDraft.smsHttpAuthToken.trim()
      }
      if (integrationCredentialDraft.voiceHttpAuthToken.trim()) {
        patch.voice_http_auth_token = integrationCredentialDraft.voiceHttpAuthToken.trim()
      }
      if (integrationCredentialDraft.whatsappAccessToken.trim()) {
        patch.whatsapp_access_token = integrationCredentialDraft.whatsappAccessToken.trim()
      }
      if (integrationCredentialDraft.facebookPageAccessToken.trim()) {
        patch.facebook_page_access_token = integrationCredentialDraft.facebookPageAccessToken.trim()
      }
      if (integrationCredentialDraft.instagramAccessToken.trim()) {
        patch.instagram_access_token = integrationCredentialDraft.instagramAccessToken.trim()
      }
      const updated = await patchBackendIntegrationCredentialSettings(patch, backendSession)
      setIntegrationCredentialDraft({
        aiProvider: updated.ai_provider,
        anthropicApiKey: '',
        anthropicApiBaseUrl: updated.anthropic_api_base_url,
        anthropicModel: updated.anthropic_model,
        clearAnthropicApiKey: false,
        alertWebhookUrl: updated.alert_webhook_url,
        alertWebhookSecret: '',
        alertDeliveryMinSeverity: updated.alert_delivery_min_severity,
        clearAlertWebhookSecret: false,
        smsHttpEndpoint: updated.sms_http_endpoint,
        smsHttpAuthToken: '',
        smsHttpFrom: updated.sms_http_from,
        smsHttpAuthHeader: updated.sms_http_auth_header,
        smsHttpAuthScheme: updated.sms_http_auth_scheme,
        smsHttpDeliveryCallbackUrl: updated.sms_http_delivery_callback_url,
        clearSmsHttpAuthToken: false,
        voiceHttpEndpoint: updated.voice_http_endpoint,
        voiceHttpAuthToken: '',
        voiceHttpFrom: updated.voice_http_from,
        voiceHttpAuthHeader: updated.voice_http_auth_header,
        voiceHttpAuthScheme: updated.voice_http_auth_scheme,
        voiceHttpStatusCallbackUrl: updated.voice_http_status_callback_url,
        clearVoiceHttpAuthToken: false,
        whatsappCloudApiBaseUrl: updated.whatsapp_cloud_api_base_url,
        whatsappPhoneNumberId: updated.whatsapp_phone_number_id,
        whatsappAccessToken: '',
        whatsappPreviewUrls: updated.whatsapp_preview_urls,
        clearWhatsappAccessToken: false,
        facebookGraphApiBaseUrl: updated.facebook_graph_api_base_url,
        facebookPageId: updated.facebook_page_id,
        facebookPageAccessToken: '',
        facebookMessagingType: updated.facebook_messaging_type,
        clearFacebookPageAccessToken: false,
        instagramGraphApiBaseUrl: updated.instagram_graph_api_base_url,
        instagramBusinessAccountId: updated.instagram_business_account_id,
        instagramAccessToken: '',
        clearInstagramAccessToken: false,
      })
      setPrototypeNotice('Production credentials saved.')
      await refreshBackend()
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Credential save failed.')
    } finally {
      setIntegrationCredentialBusy(false)
    }
  }

  async function handleProductionAccountRefresh() {
    if (!backendSession || productionAccountBusy) return
    setProductionAccountBusy(true)
    try {
      const pack = await fetchBackendProductionAccountRequests(backendSession)
      setProductionAccountPack(pack)
      setPrototypeNotice('Account request pack refreshed.')
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Account request refresh failed.')
    } finally {
      setProductionAccountBusy(false)
    }
  }

  async function handleProductionAccountCopy() {
    if (!productionAccountPack) {
      setPrototypeNotice('Account request pack is not loaded yet.')
      return
    }
    try {
      await navigator.clipboard.writeText(productionAccountPack.body)
      setPrototypeNotice('Account request body copied.')
    } catch {
      setPrototypeNotice('Clipboard unavailable; open the email draft instead.')
    }
  }

  async function handleProductionAccountSend() {
    if (!backendSession || productionAccountSendBusy) return
    setProductionAccountSendBusy(true)
    try {
      const delivery = await sendBackendProductionAccountRequestEmail(backendSession)
      setProductionAccountDelivery(delivery)
      setProductionAccountPack(delivery.pack)
      setPrototypeNotice(
        delivery.already_queued
          ? `Account request already queued on ${delivery.ticket_public_id}.`
          : `Account request queued on ${delivery.ticket_public_id}.`,
      )
      const checklist = await fetchBackendProductionReadinessChecklist(backendSession)
      setProductionReadinessChecklist(checklist)
      await refreshBackend()
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Account request email queue failed.')
    } finally {
      setProductionAccountSendBusy(false)
    }
  }

  async function refreshProductionAccountReferences() {
    if (!backendSession) return
    const [references, docs, checklist] = await Promise.all([
      fetchBackendProductionAccountReferences(backendSession),
      fetchBackendProductionAccountReferenceDocs(backendSession),
      fetchBackendProductionReadinessChecklist(backendSession),
    ])
    setProductionAccountReferences(references)
    setProductionAccountReferenceDocs(docs)
    setProductionReadinessChecklist(checklist)
  }

  async function handleProductionReadinessRefresh() {
    if (!backendSession || productionReadinessBusy) return
    setProductionReadinessBusy(true)
    try {
      const checklist = await fetchBackendProductionReadinessChecklist(backendSession)
      setProductionReadinessChecklist(checklist)
      setPrototypeNotice('Production readiness checklist refreshed.')
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Production readiness refresh failed.')
    } finally {
      setProductionReadinessBusy(false)
    }
  }

  async function handleProductionAccountReferenceSave(event: FormEvent) {
    event.preventDefault()
    if (!backendSession || productionAccountReferenceBusy) return
    if (!productionAccountReferenceDraft.accountName.trim()) {
      setPrototypeNotice('Account name is required.')
      return
    }
    setProductionAccountReferenceBusy(true)
    try {
      await createBackendProductionAccountReference(
        {
          provider: productionAccountReferenceDraft.provider,
          area: productionAccountReferenceDraft.area,
          account_name: productionAccountReferenceDraft.accountName,
          account_identifier: productionAccountReferenceDraft.accountIdentifier,
          status: productionAccountReferenceDraft.status,
          owner_email: productionAccountReferenceDraft.ownerEmail || null,
          credential_reference: productionAccountReferenceDraft.credentialReference,
          docs_reference: productionAccountReferenceDraft.docsReference,
          callback_urls: productionAccountReferenceDraft.callbackUrls
            .split('\n')
            .map((item) => item.trim())
            .filter(Boolean),
          notes: productionAccountReferenceDraft.notes,
        },
        backendSession,
      )
      setProductionAccountReferenceDraft((current) => ({
        ...current,
        accountName: '',
        accountIdentifier: '',
        ownerEmail: '',
        credentialReference: '',
        callbackUrls: '',
        notes: '',
      }))
      await refreshProductionAccountReferences()
      setPrototypeNotice('Production account reference saved.')
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Account reference save failed.')
    } finally {
      setProductionAccountReferenceBusy(false)
    }
  }

  async function handleProductionAccountReferenceStatus(
    reference: BackendProductionAccountReference,
    status: BackendProductionAccountReferenceStatus,
  ) {
    if (!backendSession || productionAccountReferenceBusy) return
    setProductionAccountReferenceBusy(true)
    try {
      await patchBackendProductionAccountReference(reference.id, { status }, backendSession)
      await refreshProductionAccountReferences()
      setPrototypeNotice(`${reference.account_name} marked ${titleCase(status)}.`)
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Account reference update failed.')
    } finally {
      setProductionAccountReferenceBusy(false)
    }
  }

  async function handleProductionAccountReferenceDocsCopy() {
    const markdown = productionAccountReferenceDocs?.markdown
    if (!markdown) {
      setPrototypeNotice('No account reference snippet is available yet.')
      return
    }
    try {
      await navigator.clipboard.writeText(markdown)
      setPrototypeNotice('Account reference snippet copied.')
    } catch {
      setPrototypeNotice('Clipboard unavailable.')
    }
  }

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

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (userActionBusy) return
    const name = newUser.name.trim()
    const email = newUser.email.trim().toLowerCase()
    const temporaryPassword = newUser.temporaryPassword.trim()
    if (!name || !email || temporaryPassword.length < 8 || !currentMarket) return

    const marketIds = newUser.marketIds.length > 0 ? newUser.marketIds : [currentMarket.id]
    const defaultMarketId = marketIds.includes(newUser.defaultMarketId)
      ? newUser.defaultMarketId
      : marketIds[0]

    setUserActionBusy(true)
    try {
      const saved = await createUser({
        name,
        email,
        temporary_password: temporaryPassword,
        role: newUser.role,
        market_ids: marketIds,
        default_market_id: defaultMarketId,
        permission_profile: newUser.permissionProfile,
        active: true,
      })
      if (saved) {
        setNewUser({
          name: '',
          email: '',
          temporaryPassword: '',
          role: 'agent',
          permissionProfile: 'role_default',
          marketIds: [currentMarket.id],
          defaultMarketId: currentMarket.id,
        })
        setAddUserOpen(false)
        setPrototypeNotice('User saved with a temporary password.')
      }
    } finally {
      setUserActionBusy(false)
    }
  }

  function toggleSupportGroupDraftChannel(channelId: ChannelId) {
    setSupportGroupDraft((current) => ({
      ...current,
      channels: current.channels.includes(channelId)
        ? current.channels.filter((item) => item !== channelId)
        : [...current.channels, channelId],
    }))
  }

  async function handleCreateSupportGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (groupActionBusy) return
    const name = supportGroupDraft.name.trim()
    if (!name) return
    const skills = supportGroupDraft.skills
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    setGroupActionBusy(true)
    try {
      const saved = await createSupportGroup({
        name,
        description: supportGroupDraft.description.trim(),
        team_email: supportGroupDraft.teamEmail.trim() || null,
        channels: supportGroupDraft.channels.map(backendChannelId),
        skills,
        active: true,
      })
      if (saved) {
        setSupportGroupDraft({ name: '', description: '', teamEmail: '', skills: '', channels: [] })
        setPrototypeNotice('Support group saved.')
      }
    } finally {
      setGroupActionBusy(false)
    }
  }

  async function handleToggleSupportGroup(groupId: string, active: boolean) {
    if (groupActionBusy) return
    setGroupActionBusy(true)
    try {
      const saved = await updateSupportGroup(groupId, { active })
      if (saved) {
        setPrototypeNotice(`Support group ${active ? 'activated' : 'paused'}.`)
      }
    } finally {
      setGroupActionBusy(false)
    }
  }

  function toggleSlaPolicyDraftChannel(channelId: ChannelId) {
    setSlaPolicyDraft((current) => ({
      ...current,
      channels: current.channels.includes(channelId)
        ? current.channels.filter((item) => item !== channelId)
        : [...current.channels, channelId],
    }))
  }

  async function handleCreateSlaPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (slaPolicyActionBusy) return
    const name = slaPolicyDraft.name.trim()
    if (!name) return
    setSlaPolicyActionBusy(true)
    try {
      const saved = await createSlaPolicy({
        name,
        priority: backendPriorityId(slaPolicyDraft.priority),
        first_response_minutes: Math.max(1, Number(slaPolicyDraft.firstResponseMinutes)),
        resolution_minutes: Math.max(1, Number(slaPolicyDraft.resolutionMinutes)),
        business_hours: slaPolicyDraft.businessHours.trim() || 'Business hours',
        channels: slaPolicyDraft.channels.map(backendChannelId),
        active: slaPolicyDraft.active,
        position: Number(slaPolicyDraft.position) || 100,
      })
      if (saved) {
        setSlaPolicyDraft({
          name: '',
          priority: 'medium',
          firstResponseMinutes: 60,
          resolutionMinutes: 1440,
          businessHours: 'Business hours',
          channels: [],
          active: true,
          position: 40,
        })
        setAddSlaPolicyOpen(false)
        setPrototypeNotice('SLA policy saved.')
      }
    } finally {
      setSlaPolicyActionBusy(false)
    }
  }

  async function handleToggleSlaPolicy(policyId: string, active: boolean) {
    if (slaPolicyActionBusy) return
    setSlaPolicyActionBusy(true)
    try {
      const saved = await updateSlaPolicy(policyId, { active })
      if (saved) {
        setPrototypeNotice(`SLA policy ${active ? 'activated' : 'paused'}.`)
      }
    } finally {
      setSlaPolicyActionBusy(false)
    }
  }

  function toggleTicketFieldDraftChannel(channelId: ChannelId) {
    setTicketFieldDraft((current) => ({
      ...current,
      channels: current.channels.includes(channelId)
        ? current.channels.filter((item) => item !== channelId)
        : [...current.channels, channelId],
    }))
  }

  async function handleCreateTicketField(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const label = ticketFieldDraft.label.trim()
    const key = normalizeTicketFieldKey(ticketFieldDraft.key || label)
    const options = ticketFieldOptions(ticketFieldDraft.options)
    if (!label || !key) return
    if (
      (ticketFieldDraft.fieldType === 'select' || ticketFieldDraft.fieldType === 'multiselect') &&
      options.length === 0
    ) {
      setPrototypeNotice('Select fields need at least one option.')
      return
    }

    const saved = await createTicketField({
      key,
      label,
      field_type: ticketFieldDraft.fieldType,
      required: ticketFieldDraft.required,
      active: ticketFieldDraft.active,
      options,
      channels: ticketFieldDraft.channels.map(backendChannelId),
      position: ticketFieldDraft.position,
    })
    if (!saved) return
    setTicketFieldDraft({
      label: '',
      key: '',
      fieldType: 'text',
      options: '',
      channels: [],
      required: false,
      active: true,
      position: 100,
    })
    setPrototypeNotice('Ticket field saved.')
  }

  async function handleChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (userActionBusy) return
    if (passwordChange.currentPassword.length < 1 || passwordChange.newPassword.length < 8) return
    setUserActionBusy(true)
    try {
      const saved = await changePassword(passwordChange.currentPassword, passwordChange.newPassword)
      if (saved) {
        setPasswordChange({ currentPassword: '', newPassword: '' })
        setPrototypeNotice('Your password was updated.')
      }
    } finally {
      setUserActionBusy(false)
    }
  }

  function updateUserPermissionOverride(
    user: BackendUser,
    permission: BackendPermission,
    mode: 'default' | 'allow' | 'deny',
  ) {
    const allow = user.permission_overrides.allow.filter((item) => item !== permission)
    const deny = user.permission_overrides.deny.filter((item) => item !== permission)
    if (mode === 'allow') allow.push(permission)
    if (mode === 'deny') deny.push(permission)
    updateUser(user.id, {
      permission_profile: mode === 'default' ? user.permission_profile : 'custom',
      permission_overrides: { allow, deny },
    })
  }

  async function handleStartMfaEnrollment() {
    const enrollment = await enrollMfa()
    if (!enrollment) return
    setMfaEnrollment(enrollment)
    setMfaConfirmCode('')
    setPrototypeNotice('MFA enrollment started.')
  }

  async function handleConfirmMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const code = mfaConfirmCode.trim()
    if (code.length < 6) return
    const confirmed = await confirmMfa(code)
    if (!confirmed) return
    setMfaEnrollment(null)
    setMfaConfirmCode('')
    setPrototypeNotice('MFA is now enabled.')
  }

  async function handleDisableMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (mfaDisable.currentPassword.length < 1) return
    const disabled = await disableMfa(mfaDisable.currentPassword, mfaDisable.code.trim())
    if (!disabled) return
    setMfaDisable({ currentPassword: '', code: '' })
    setMfaEnrollment(null)
    setPrototypeNotice('MFA was disabled.')
  }

  async function handleOperationalAlertUpdate(
    alert: BackendOperationalAlert,
    status: BackendOperationalAlertStatus,
  ) {
    const saved = await updateOperationalAlertStatus(
      alert.id,
      status,
      `${titleCase(status)} from Omni Setup operations panel.`,
    )
    if (saved) {
      setPrototypeNotice(`Operational alert ${titleCase(status).toLowerCase()}.`)
    }
  }

  function updatePortalDraft(patch: Partial<typeof portalDraft>) {
    setPortalDraft((current) => ({ ...current, ...patch }))
  }

  function updatePortalCustomField(field: BackendTicketField, value: unknown) {
    setPortalDraft((current) => ({
      ...current,
      customFields: {
        ...current.customFields,
        [field.key]: value,
      },
    }))
  }

  function portalCustomFieldIsMissing(field: BackendTicketField, value: unknown) {
    if (field.field_type === 'checkbox') return value !== true
    return value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0)
  }

  function compactPortalCustomFields() {
    return Object.fromEntries(
      Object.entries(portalDraft.customFields).filter(([, value]) => {
        if (Array.isArray(value)) return value.length > 0
        return value !== undefined && value !== null && value !== ''
      }),
    )
  }

  function renderPortalFieldInput(field: BackendTicketField) {
    const id = `portal-field-${field.id}`
    const value = portalDraft.customFields[field.key]
    if (field.field_type === 'select') {
      return (
        <select
          id={id}
          value={typeof value === 'string' ? value : ''}
          required={field.required}
          onChange={(event) => updatePortalCustomField(field, event.target.value)}
        >
          <option value="">Not set</option>
          {field.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      )
    }
    if (field.field_type === 'multiselect') {
      const currentValues = Array.isArray(value) ? value.map(String) : []
      return (
        <div className="portal-field-options" id={id}>
          {field.options.map((option) => (
            <label key={option}>
              <input
                type="checkbox"
                checked={currentValues.includes(option)}
                onChange={(event) => {
                  updatePortalCustomField(
                    field,
                    event.target.checked
                      ? [...currentValues, option]
                      : currentValues.filter((item) => item !== option),
                  )
                }}
              />
              {option}
            </label>
          ))}
        </div>
      )
    }
    if (field.field_type === 'checkbox') {
      return (
        <label className="portal-field-check" htmlFor={id}>
          <input
            id={id}
            type="checkbox"
            checked={value === true}
            required={field.required}
            onChange={(event) => updatePortalCustomField(field, event.target.checked)}
          />
          <span>{field.placeholder || field.help_text || field.label}</span>
        </label>
      )
    }
    if (field.field_type === 'textarea') {
      return (
        <textarea
          id={id}
          required={field.required}
          value={typeof value === 'string' ? value : ''}
          placeholder={field.placeholder}
          onChange={(event) => updatePortalCustomField(field, event.target.value)}
        />
      )
    }
    return (
      <input
        id={id}
        required={field.required}
        type={field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text'}
        value={value === undefined || value === null ? '' : String(value)}
        placeholder={field.placeholder}
        onChange={(event) => {
          if (field.field_type === 'number') {
            updatePortalCustomField(field, event.target.value === '' ? '' : Number(event.target.value))
            return
          }
          updatePortalCustomField(field, event.target.value)
        }}
      />
    )
  }

  async function uploadPortalAttachment(publicId: string, email: string, file: File | null) {
    if (!file) return ''
    const attachment = await uploadBackendPortalAttachment(portalMarket, publicId, email, file)
    if (attachment.scan_status === 'clean') {
      return `${attachment.filename} was attached.`
    }
    return `${attachment.filename} was received and marked ${titleCase(attachment.scan_status)}.`
  }

  async function handlePortalTicketSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (portalSubmitting) return
    const name = portalDraft.name.trim()
    const email = portalDraft.email.trim().toLowerCase()
    const subject = portalDraft.subject.trim()
    const description = portalDraft.description.trim()
    if (!name || !email || !subject || !description) {
      setPortalNotice('Name, email, subject, and details are required.')
      return
    }
    const missingField = portalTicketFields.find((field) =>
      field.required && portalCustomFieldIsMissing(field, portalDraft.customFields[field.key]),
    )
    if (missingField) {
      setPortalNotice(`${missingField.label} is required.`)
      return
    }

    setPortalSubmitting(true)
    setPortalNotice('')
    try {
      const response = await createBackendPortalTicket(portalMarket, {
        name,
        email,
        phone: portalDraft.phone.trim() || undefined,
        subject,
        description,
        priority: portalDraft.priority,
        custom_fields: compactPortalCustomFields(),
        search_query: portalQuery.trim() || subject,
      })
      if (response.article_suggestions.length) {
        setPortalAnswers(response.article_suggestions)
      }
      let attachmentMessage = ''
      if (portalAttachmentFile) {
        try {
          attachmentMessage = ` ${await uploadPortalAttachment(response.public_id, email, portalAttachmentFile)}`
          setPortalAttachmentFile(null)
        } catch (uploadError) {
          attachmentMessage = ` Ticket created, but the attachment failed: ${
            uploadError instanceof Error ? uploadError.message : 'upload failed'
          }.`
        }
      }
      setPortalNotice(`Ticket ${response.public_id} was created. Our support team has the details.${attachmentMessage}`)
      setPortalLookup({ publicId: response.public_id, email })
      setPortalTicketDetail(null)
      setPortalLookupNotice('Use the check-ticket panel to follow progress or add more details.')
      setPortalDraft((current) => ({
        ...current,
        subject: '',
        description: '',
        priority: 'normal',
        customFields: {},
      }))
    } catch (error) {
      setPortalNotice(error instanceof Error ? error.message : 'Ticket submission failed.')
    } finally {
      setPortalSubmitting(false)
    }
  }

  async function handlePortalTicketLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (portalLookupBusy) return
    const publicId = portalLookup.publicId.trim().toUpperCase()
    const email = portalLookup.email.trim().toLowerCase()
    if (!publicId || !email) {
      setPortalLookupNotice('Ticket number and email are required.')
      return
    }
    setPortalLookupBusy(true)
    setPortalLookupNotice('')
    try {
      const detail = await fetchBackendPortalTicket(portalMarket, publicId, email)
      setPortalTicketDetail(detail)
      setPortalReplyBody('')
      setPortalAnswers(detail.article_suggestions)
      setPortalLookup((current) => ({ ...current, publicId: detail.public_id, email }))
      setPortalLookupNotice(`Ticket ${detail.public_id} is ${detail.customer_status.toLowerCase()}.`)
    } catch (error) {
      setPortalTicketDetail(null)
      setPortalLookupNotice(error instanceof Error ? error.message : 'Ticket lookup failed.')
    } finally {
      setPortalLookupBusy(false)
    }
  }

  async function handlePortalTicketReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (portalReplyBusy || !portalTicketDetail) return
    const email = portalLookup.email.trim().toLowerCase()
    const body = portalReplyBody.trim()
    const replyAttachment = portalReplyAttachmentFile
    if (!email || (body.length < 2 && !replyAttachment)) {
      setPortalLookupNotice('Add a reply or attachment before sending.')
      return
    }
    setPortalReplyBusy(true)
    setPortalLookupNotice('')
    try {
      let detail = await createBackendPortalTicketReply(
        portalMarket,
        portalTicketDetail.public_id,
        { email, body: body || `Attachment added: ${replyAttachment?.name ?? 'customer file'}.` },
      )
      let attachmentMessage = ''
      if (replyAttachment) {
        try {
          attachmentMessage = ` ${await uploadPortalAttachment(detail.public_id, email, replyAttachment)}`
          setPortalReplyAttachmentFile(null)
          detail = await fetchBackendPortalTicket(portalMarket, detail.public_id, email)
        } catch (uploadError) {
          attachmentMessage = ` Reply added, but the attachment failed: ${
            uploadError instanceof Error ? uploadError.message : 'upload failed'
          }.`
        }
      }
      setPortalTicketDetail(detail)
      setPortalReplyBody('')
      setPortalAnswers(detail.article_suggestions)
      setPortalLookupNotice(
        `Reply added. Ticket ${detail.public_id} is ${detail.customer_status.toLowerCase()}.${attachmentMessage}`,
      )
    } catch (error) {
      setPortalLookupNotice(error instanceof Error ? error.message : 'Reply failed.')
    } finally {
      setPortalReplyBusy(false)
    }
  }

  function renderPortalHelpCenter() {
    const portalBrandName = workspaceSettings?.public_brand_name?.trim() || 'Omni Ticket'
    const portalSupportName = workspaceSettings?.portal_support_name?.trim() || 'Wakanow support'
    const portalAccent = workspaceSettings?.portal_primary_color?.trim() || '#0b5eea'
    const portalWelcome =
      workspaceSettings?.portal_welcome_message?.trim() ||
      'Search answers or raise a support ticket'
    const portalLogoUrl = workspaceSettings?.portal_logo_url?.trim() || ''
    return (
      <main className="portal-shell" style={{ ['--portal-accent' as string]: portalAccent }}>
        <header className="portal-topbar">
          <a className="portal-brand" href={routeHref({ screen: 'portal' })}>
            <span className="brand-mark" style={{ background: portalAccent }}>
              {portalLogoUrl ? (
                <img src={portalLogoUrl} alt={`${portalBrandName} logo`} />
              ) : (
                <LifeBuoy size={22} />
              )}
            </span>
            <span>
              <strong>{portalBrandName}</strong>
              <small>{portalSupportName}</small>
            </span>
          </a>
          <div className="portal-topbar-actions">
            <label>
              <span>Market</span>
              <select
                value={portalMarket}
                onChange={(event) => {
                  setPortalMarket(event.target.value)
                  setPortalTicketDetail(null)
                  setPortalLookupNotice('')
                }}
              >
                {portalMarketOptions.map((market) => (
                  <option key={market.code} value={market.code}>
                    {market.label}
                  </option>
                ))}
              </select>
            </label>
            <a className="secondary-action" href={routeHref({ screen: 'command' })}>
              <Lock size={16} />
              Staff sign in
            </a>
          </div>
        </header>

        <section className="portal-hero">
          <div className="portal-hero-copy">
            <span className="section-kicker">Help Center</span>
            <h1>{portalWelcome}</h1>
            <form className="portal-search" onSubmit={(event) => event.preventDefault()}>
              <Search size={20} />
              <input
                value={portalQuery}
                onChange={(event) => setPortalQuery(event.target.value)}
                placeholder="Search payments, refunds, booking changes"
                aria-label="Search Help Center answers"
              />
              {portalLoading ? <RefreshCw size={18} className="spin-icon" /> : null}
            </form>
            {portalSearchError ? <strong className="portal-error">{portalSearchError}</strong> : null}
          </div>
          <div className="portal-service-strip" aria-label="Support routes">
            <article>
              <Mail size={18} />
              <strong>Email</strong>
              <span>Support receives a ticket copy.</span>
            </article>
            <article>
              <Globe2 size={18} />
              <strong>Portal</strong>
              <span>Market-specific routing and fields.</span>
            </article>
            <article>
              <BookOpen size={18} />
              <strong>Answers</strong>
              <span>Approved guidance before submission.</span>
            </article>
          </div>
        </section>

        <section className="portal-workspace">
          <div className="portal-column">
            <section className="portal-panel portal-results" aria-label="Suggested answers">
              <div className="portal-section-head">
                <div>
                  <span>Suggested answers</span>
                  <h2>{portalAnswers.length ? `${portalAnswers.length} article(s) found` : 'No matching answer yet'}</h2>
                </div>
                <BookOpen size={20} />
              </div>
              <div className="portal-answer-list">
                {portalAnswers.map((answer) => (
                  <article className="portal-answer-card" key={answer.article_id}>
                    <div>
                      <strong>{answer.title}</strong>
                      <small>
                        Updated {formatTime(answer.updated_at)}
                        {answer.language ? ` · ${answer.language.toUpperCase()}` : ''}
                      </small>
                    </div>
                    <p>{answer.body.length > 320 ? `${answer.body.slice(0, 317)}...` : answer.body}</p>
                    <div className="portal-answer-meta">
                      {answer.reasons.slice(0, 2).map((reason) => (
                        <span key={reason}>{reason}</span>
                      ))}
                      {answer.tags.slice(0, 3).map((tag) => (
                        <span key={tag}>{tag}</span>
                      ))}
                    </div>
                  </article>
                ))}
                {!portalLoading && portalAnswers.length === 0 ? (
                  <article className="portal-empty">
                    <MessageSquare size={18} />
                    <span>Create a ticket and the support team will follow up.</span>
                  </article>
                ) : null}
              </div>
            </section>

            <section className="portal-panel portal-status-panel" aria-label="Ticket status">
              <div className="portal-section-head">
                <div>
                  <span>Ticket status</span>
                  <h2>Check progress</h2>
                </div>
                <Clock size={20} />
              </div>
              <form className="portal-lookup-form" onSubmit={handlePortalTicketLookup}>
                <label>
                  Ticket number
                  <input
                    value={portalLookup.publicId}
                    onChange={(event) =>
                      setPortalLookup((current) => ({ ...current, publicId: event.target.value }))
                    }
                    placeholder="OMNI-1005"
                    required
                  />
                </label>
                <label>
                  Email
                  <input
                    type="email"
                    value={portalLookup.email}
                    onChange={(event) =>
                      setPortalLookup((current) => ({ ...current, email: event.target.value }))
                    }
                    required
                  />
                </label>
                <button className="secondary-action" type="submit" disabled={portalLookupBusy}>
                  {portalLookupBusy ? <RefreshCw size={16} className="spin-icon" /> : <Search size={16} />}
                  Check
                </button>
              </form>
              {portalLookupNotice ? <strong className="portal-notice">{portalLookupNotice}</strong> : null}
              {portalTicketDetail ? (
                <div className="portal-ticket-detail">
                  <div className="portal-ticket-summary">
                    <em className={`chip status-${portalTicketDetail.status === 'open' ? 'healthy' : portalTicketDetail.status === 'closed' ? 'done' : 'pending'}`}>
                      {portalTicketDetail.customer_status}
                    </em>
                    <strong>{portalTicketDetail.subject}</strong>
                    <p>{portalTicketDetail.description}</p>
                    <div className="portal-ticket-facts">
                      <span>
                        <b>Ticket</b>
                        {portalTicketDetail.public_id}
                      </span>
                      <span>
                        <b>Priority</b>
                        {titleCase(portalTicketDetail.priority)}
                      </span>
                      <span>
                        <b>Updated</b>
                        {formatTime(portalTicketDetail.updated_at)}
                      </span>
                    </div>
                    <small>{portalTicketDetail.next_step}</small>
                    {portalTicketDetail.attachments.length ? (
                      <div className="portal-attachment-list" aria-label="Customer attachments">
                        {portalTicketDetail.attachments.map((attachment) => (
                          <span key={attachment.id}>
                            <Paperclip size={14} />
                            {attachment.filename}
                            <small>
                              {formatFileSize(attachment.size_bytes)} · {titleCase(attachment.scan_status)}
                            </small>
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div className="portal-public-timeline" aria-label="Public ticket conversation">
                    {portalTicketDetail.timeline.map((event) => (
                      <article key={event.id}>
                        <div>
                          <strong>{event.actor}</strong>
                          <small>{formatTime(event.created_at)} · {titleCase(event.channel)}</small>
                        </div>
                        <p>{event.body}</p>
                      </article>
                    ))}
                  </div>
                  <form className="portal-reply-form" onSubmit={handlePortalTicketReply}>
                    <label>
                      Add reply
                      <textarea
                        value={portalReplyBody}
                        onChange={(event) => setPortalReplyBody(event.target.value)}
                      />
                    </label>
                    <label className="portal-file-field">
                      Attach file
                      <input
                        type="file"
                        onChange={(event) => setPortalReplyAttachmentFile(event.target.files?.[0] ?? null)}
                      />
                      {portalReplyAttachmentFile ? (
                        <small>{portalReplyAttachmentFile.name} · {formatFileSize(portalReplyAttachmentFile.size)}</small>
                      ) : null}
                    </label>
                    <button className="primary-action portal-submit" type="submit" disabled={portalReplyBusy}>
                      {portalReplyBusy ? <RefreshCw size={16} className="spin-icon" /> : <Send size={16} />}
                      Send reply
                    </button>
                  </form>
                </div>
              ) : null}
            </section>
          </div>

          <form className="portal-panel portal-ticket-form" onSubmit={handlePortalTicketSubmit}>
            <div className="portal-section-head">
              <div>
                <span>Support ticket</span>
                <h2>Send the request</h2>
              </div>
              <Send size={20} />
            </div>
            {portalNotice ? <strong className="portal-notice">{portalNotice}</strong> : null}
            <div className="portal-form-grid">
              <label>
                Name
                <input
                  value={portalDraft.name}
                  onChange={(event) => updatePortalDraft({ name: event.target.value })}
                  autoComplete="name"
                  required
                />
              </label>
              <label>
                Email
                <input
                  type="email"
                  value={portalDraft.email}
                  onChange={(event) => updatePortalDraft({ email: event.target.value })}
                  autoComplete="email"
                  required
                />
              </label>
              <label>
                Phone
                <input
                  value={portalDraft.phone}
                  onChange={(event) => updatePortalDraft({ phone: event.target.value })}
                  autoComplete="tel"
                />
              </label>
              <label>
                Priority
                <select
                  value={portalDraft.priority}
                  onChange={(event) =>
                    updatePortalDraft({
                      priority: event.target.value as NonNullable<BackendCreatePortalTicketInput['priority']>,
                    })
                  }
                >
                  {portalPriorityOptions.map((priority) => (
                    <option key={priority} value={priority}>
                      {titleCase(priority)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="span-all">
                Subject
                <input
                  value={portalDraft.subject}
                  onChange={(event) => updatePortalDraft({ subject: event.target.value })}
                  required
                />
              </label>
              <label className="span-all">
                Details
                <textarea
                  value={portalDraft.description}
                  onChange={(event) => updatePortalDraft({ description: event.target.value })}
                  required
                />
              </label>
              <label className="span-all portal-file-field">
                Attach proof
                <input
                  type="file"
                  onChange={(event) => setPortalAttachmentFile(event.target.files?.[0] ?? null)}
                />
                {portalAttachmentFile ? (
                  <small>{portalAttachmentFile.name} · {formatFileSize(portalAttachmentFile.size)}</small>
                ) : null}
              </label>
            </div>
            {portalTicketFields.length ? (
              <div className="portal-custom-fields" aria-label="Ticket details">
                {portalTicketFields.map((field) => (
                  <label className={field.field_type === 'textarea' ? 'span-all' : ''} key={field.id}>
                    <span>
                      {field.label}
                      {field.required ? <em>Required</em> : null}
                    </span>
                    {renderPortalFieldInput(field)}
                    {field.help_text ? <small>{field.help_text}</small> : null}
                  </label>
                ))}
              </div>
            ) : null}
            <button
              className="primary-action portal-submit"
              type="submit"
              disabled={portalSubmitting}
            >
              {portalSubmitting ? <RefreshCw size={16} className="spin-icon" /> : <Send size={16} />}
              Submit ticket
            </button>
          </form>
        </section>
      </main>
    )
  }

  if (isPortalRoute) {
    return renderPortalHelpCenter()
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
              login({
                email: loginEmail,
                password: loginPassword,
                market_id: loginMarket,
                mfa_code: loginMfaCode.trim() || undefined,
              })
            }}
          >
            <label>
              Email
              <input
                type="email"
                value={loginEmail}
                onChange={(event) => {
                  setLoginEmail(event.target.value)
                }}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => {
                  setLoginPassword(event.target.value)
                }}
              />
            </label>
            <label>
              Verification code
              <input
                inputMode="numeric"
                value={loginMfaCode}
                onChange={(event) => {
                  setLoginMfaCode(event.target.value)
                }}
                placeholder="Authenticator code"
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
          <div className="login-sso-panel">
            <div>
              <strong>{oidcProviderConfig?.provider_name ?? 'Enterprise SSO'}</strong>
              <span>{oidcProviderConfig?.notes ?? 'Checking identity provider readiness.'}</span>
            </div>
            <button
              type="button"
              disabled={!oidcProviderConfig?.login_available || backendSync.status === 'syncing'}
              onClick={() => {
                beginOidcLogin(loginMarket)
              }}
            >
              <ShieldCheck size={16} />
              Continue with SSO
            </button>
          </div>
          {backendSync.error ? <strong className="login-error">{backendSync.error}</strong> : null}
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

  function addTodo() {
    const label = todoDraft.trim()
    if (!label) return
    setTodos((current) => [...current, { id: makeTodoId(), label, done: false }])
    setTodoDraft('')
  }

  function toggleTodo(id: string) {
    setTodos((current) =>
      current.map((todo) => (todo.id === id ? { ...todo, done: !todo.done } : todo)),
    )
  }

  function removeTodo(id: string) {
    setTodos((current) => current.filter((todo) => todo.id !== id))
  }

  function exportTicketsCsv(rows: OmniConversation[]) {
    if (typeof window === 'undefined') return
    const header = [
      'Ticket',
      'Subject',
      'Status',
      'Priority',
      'Channel',
      'Group',
      'Owner',
      'Customer',
      'Created',
      'Resolution due',
    ]
    const body = rows.map((conversation) => {
      const owner = state.agents.find((agent) => agent.id === conversation.assigneeId)
      const customer = state.customers.find((entry) => entry.id === conversation.customerId)
      return [
        conversation.ticketNumber,
        conversation.subject,
        conversation.status,
        conversation.priority,
        conversation.channelId,
        conversation.group,
        owner?.name ?? 'Unassigned',
        customer?.name ?? '',
        conversation.createdAt,
        conversation.resolutionDue,
      ]
    })
    const csv = [header, ...body]
      .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
      .join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `omni-tickets-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    announcePrototype(`Exported ${rows.length} ticket${rows.length === 1 ? '' : 's'} to CSV.`)
  }

  function toggleTicketSelection(id: string) {
    setSelectedTicketIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  function toggleSelectAllTickets(ids: string[]) {
    setSelectedTicketIds((current) => (ids.length > 0 && ids.every((id) => current.includes(id)) ? [] : ids))
  }

  function applyBulkTicketUpdate(patch: Partial<OmniConversation>) {
    selectedTicketIds.forEach((id) => updateConversation(id, patch))
    setSelectedTicketIds([])
  }

  function resetAllInboxFilters() {
    resetFilters()
    setInboxGroup('all')
    setInboxCreated('all')
    setInboxDue('any')
  }

  function addTimeLog(ticketId: string) {
    const minutes = Number.parseInt(timeLogDraft, 10)
    if (!Number.isFinite(minutes) || minutes <= 0) return
    const agent = backendSession?.user.name ?? backendSession?.user.email ?? 'You'
    const entry: TicketTimeLog = { id: makeTodoId(), minutes, agent, at: new Date().toISOString() }
    setTimeLogs((current) => ({ ...current, [ticketId]: [...(current[ticketId] ?? []), entry] }))
    setTimeLogDraft('')
  }

  function removeTimeLog(ticketId: string, id: string) {
    setTimeLogs((current) => ({
      ...current,
      [ticketId]: (current[ticketId] ?? []).filter((log) => log.id !== id),
    }))
  }

  async function handleCreateBusinessHours(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = businessHoursName.trim()
    if (name.length < 2) return
    const saved = await createBusinessHours({
      name,
      timezone: businessHoursTimezone.trim() || 'Africa/Lagos',
    })
    if (saved) {
      setBusinessHoursName('')
      setPrototypeNotice('Business hours saved.')
    }
  }

  async function toggleBusinessHoursActive(calendar: BusinessHours) {
    const saved = await updateBusinessHours(calendar.id, { active: !calendar.active })
    if (saved) setPrototypeNotice(`Business hours ${calendar.active ? 'paused' : 'activated'}.`)
  }

  function businessHoursDraftFor(calendar: BusinessHours): BusinessHoursDay[] {
    return businessHoursDrafts[calendar.id] ?? calendar.days
  }

  function setBusinessHoursDayField(
    calendar: BusinessHours,
    index: number,
    patch: Partial<BusinessHoursDay>,
  ) {
    const current = businessHoursDraftFor(calendar)
    setBusinessHoursDrafts((drafts) => ({
      ...drafts,
      [calendar.id]: current.map((day, dayIndex) => (dayIndex === index ? { ...day, ...patch } : day)),
    }))
  }

  async function saveBusinessHoursSchedule(calendar: BusinessHours) {
    const days = businessHoursDrafts[calendar.id]
    if (!days) return
    const saved = await updateBusinessHours(calendar.id, { days })
    if (saved) {
      setBusinessHoursDrafts((drafts) => {
        const next = { ...drafts }
        delete next[calendar.id]
        return next
      })
      setPrototypeNotice('Business hours schedule saved.')
    }
  }

  async function handleCreateCannedResponse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = cannedDraft.name.trim()
    const body = cannedDraft.body.trim()
    if (name.length < 2 || body.length < 2 || cannedBusy) return
    setCannedBusy(true)
    try {
      const saved = await createResponseMacro({
        name,
        body,
        shortcut: cannedDraft.shortcut.trim() || null,
      })
      if (saved) {
        setCannedDraft({ name: '', shortcut: '', body: '' })
        setPrototypeNotice('Canned response saved.')
      }
    } finally {
      setCannedBusy(false)
    }
  }

  async function toggleCannedResponse(macro: ResponseMacro) {
    if (cannedBusy) return
    setCannedBusy(true)
    try {
      const saved = await updateResponseMacro(macro.id, { active: !macro.active })
      if (saved) setPrototypeNotice(`Canned response ${macro.active ? 'paused' : 'activated'}.`)
    } finally {
      setCannedBusy(false)
    }
  }

  function startEditCanned(macro: ResponseMacro) {
    setCannedEditId(macro.id)
    setCannedEditDraft({ name: macro.name, shortcut: macro.shortcut ?? '', body: macro.body })
  }

  async function saveCannedEdit(macroId: string) {
    const name = cannedEditDraft.name.trim()
    const body = cannedEditDraft.body.trim()
    if (name.length < 2 || body.length < 2 || cannedBusy) return
    setCannedBusy(true)
    try {
      const saved = await updateResponseMacro(macroId, {
        name,
        body,
        shortcut: cannedEditDraft.shortcut.trim() || null,
      })
      if (saved) {
        setCannedEditId('')
        setPrototypeNotice('Canned response updated.')
      }
    } finally {
      setCannedBusy(false)
    }
  }

  async function handleCreateTicketTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = templateDraft.name.trim()
    const subject = templateDraft.subject.trim()
    if (name.length < 2 || subject.length < 1 || templateBusy) return
    setTemplateBusy(true)
    try {
      const tags = templateDraft.tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean)
      const saved = await createTicketTemplate({
        name,
        subject,
        description: templateDraft.description.trim(),
        priority: backendPriorityId(templateDraft.priority),
        group: templateDraft.group.trim(),
        tags,
      })
      if (saved) {
        setTemplateDraft({ name: '', subject: '', description: '', priority: 'medium', group: '', tags: '' })
        setPrototypeNotice('Ticket template saved.')
      }
    } finally {
      setTemplateBusy(false)
    }
  }

  async function toggleTicketTemplate(template: TicketTemplate) {
    if (templateBusy) return
    setTemplateBusy(true)
    try {
      const saved = await updateTicketTemplate(template.id, { active: !template.active })
      if (saved) setPrototypeNotice(`Ticket template ${template.active ? 'paused' : 'activated'}.`)
    } finally {
      setTemplateBusy(false)
    }
  }

  async function handleCreateTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = tagDraft.name.trim()
    if (name.length < 1 || tagBusy) return
    setTagBusy(true)
    try {
      const saved = await createTag({
        name,
        color: tagDraft.color,
        description: tagDraft.description.trim(),
      })
      if (saved) {
        setTagDraft({ name: '', color: '#2f6fed', description: '' })
        setPrototypeNotice('Tag saved.')
      }
    } finally {
      setTagBusy(false)
    }
  }

  async function toggleTag(tag: Tag) {
    if (tagBusy) return
    setTagBusy(true)
    try {
      const saved = await updateTag(tag.id, { active: !tag.active })
      if (saved) setPrototypeNotice(`Tag ${tag.active ? 'paused' : 'activated'}.`)
    } finally {
      setTagBusy(false)
    }
  }

  async function handleCreateCsatSurvey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = surveyDraft.name.trim()
    const question = surveyDraft.question.trim()
    if (name.length < 2 || question.length < 2 || surveyBusy) return
    setSurveyBusy(true)
    try {
      const saved = await createCsatSurvey({ name, question, scale: surveyDraft.scale })
      if (saved) {
        setSurveyDraft({ name: '', question: '', scale: 5 })
        setPrototypeNotice('CSAT survey saved.')
      }
    } finally {
      setSurveyBusy(false)
    }
  }

  async function toggleCsatSurvey(survey: CsatSurvey) {
    if (surveyBusy) return
    setSurveyBusy(true)
    try {
      const saved = await updateCsatSurvey(survey.id, { active: !survey.active })
      if (saved) setPrototypeNotice(`CSAT survey ${survey.active ? 'paused' : 'activated'}.`)
    } finally {
      setSurveyBusy(false)
    }
  }

  async function handleCreateEmailNotification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = notifDraft.name.trim()
    if (name.length < 2 || notifBusy) return
    setNotifBusy(true)
    try {
      const recipients = notifDraft.recipients
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
      const saved = await createEmailNotification({
        name,
        event: notifDraft.event,
        recipients,
        subject: notifDraft.subject.trim(),
        body: notifDraft.body.trim(),
      })
      if (saved) {
        setNotifDraft({ name: '', event: 'ticket_created', recipients: '', subject: '', body: '' })
        setPrototypeNotice('Email notification saved.')
      }
    } finally {
      setNotifBusy(false)
    }
  }

  async function toggleEmailNotification(notification: EmailNotification) {
    if (notifBusy) return
    setNotifBusy(true)
    try {
      const saved = await updateEmailNotification(notification.id, { active: !notification.active })
      if (saved)
        setPrototypeNotice(`Email notification ${notification.active ? 'paused' : 'activated'}.`)
    } finally {
      setNotifBusy(false)
    }
  }

  function addScenarioAction() {
    const value = scenarioActionDraft.value.trim()
    if (!value) return
    setScenarioActions((current) => [...current, { type: scenarioActionDraft.type, value }])
    setScenarioActionDraft({ type: scenarioActionDraft.type, value: '' })
  }

  function removeScenarioAction(index: number) {
    setScenarioActions((current) => current.filter((_, position) => position !== index))
  }

  async function handleCreateScenarioAutomation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = scenarioDraft.name.trim()
    if (name.length < 2 || scenarioActions.length === 0 || scenarioBusy) return
    setScenarioBusy(true)
    try {
      const saved = await createScenarioAutomation({
        name,
        description: scenarioDraft.description.trim(),
        actions: scenarioActions,
      })
      if (saved) {
        setScenarioDraft({ name: '', description: '' })
        setScenarioActions([])
        setPrototypeNotice('Scenario automation saved.')
      }
    } finally {
      setScenarioBusy(false)
    }
  }

  async function toggleScenarioAutomation(scenario: ScenarioAutomation) {
    if (scenarioBusy) return
    setScenarioBusy(true)
    try {
      const saved = await updateScenarioAutomation(scenario.id, { active: !scenario.active })
      if (saved) setPrototypeNotice(`Scenario automation ${scenario.active ? 'paused' : 'activated'}.`)
    } finally {
      setScenarioBusy(false)
    }
  }

  async function handleCreateCustomField(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const key = customFieldDraft.key.trim().toLowerCase()
    const label = customFieldDraft.label.trim()
    if (!/^[a-z][a-z0-9_]{1,63}$/.test(key) || label.length < 1 || customFieldBusy) return
    const needsOptions = customFieldDraft.fieldType === 'select' || customFieldDraft.fieldType === 'multiselect'
    const options = customFieldDraft.options
      .split(',')
      .map((option) => option.trim())
      .filter(Boolean)
    if (needsOptions && options.length === 0) {
      setPrototypeNotice('Select fields need at least one option.')
      return
    }
    setCustomFieldBusy(true)
    try {
      const saved = await createCustomFieldDefinition({
        entity: customFieldEntity,
        key,
        label,
        field_type: customFieldDraft.fieldType,
        required: customFieldDraft.required,
        options: needsOptions ? options : [],
      })
      if (saved) {
        setCustomFieldDraft({ key: '', label: '', fieldType: 'text', required: false, options: '' })
        setPrototypeNotice('Custom field saved.')
      }
    } finally {
      setCustomFieldBusy(false)
    }
  }

  async function toggleCustomField(field: CustomFieldDefinition) {
    if (customFieldBusy) return
    setCustomFieldBusy(true)
    try {
      const saved = await updateCustomFieldDefinition(field.id, { active: !field.active })
      if (saved) setPrototypeNotice(`Custom field ${field.active ? 'paused' : 'activated'}.`)
    } finally {
      setCustomFieldBusy(false)
    }
  }

  function addObjectField() {
    const key = objectFieldDraft.key.trim().toLowerCase()
    if (!/^[a-z][a-z0-9_]{1,63}$/.test(key)) return
    setObjectFields((current) => [
      ...current,
      {
        key,
        label: objectFieldDraft.label.trim() || key,
        fieldType: objectFieldDraft.fieldType,
        required: false,
        options: [],
      },
    ])
    setObjectFieldDraft({ key: '', label: '', fieldType: 'text' })
  }

  function removeObjectField(index: number) {
    setObjectFields((current) => current.filter((_, position) => position !== index))
  }

  async function handleCreateCustomObject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const key = objectDraft.key.trim().toLowerCase()
    const name = objectDraft.name.trim()
    if (!/^[a-z][a-z0-9_]{1,63}$/.test(key) || name.length < 1 || objectBusy) return
    setObjectBusy(true)
    try {
      const saved = await createCustomObject({
        key,
        name,
        description: objectDraft.description.trim(),
        fields: objectFields.map((field) => ({
          key: field.key,
          label: field.label,
          field_type: field.fieldType,
          required: field.required,
          options: field.options,
        })),
      })
      if (saved) {
        setObjectDraft({ key: '', name: '', description: '' })
        setObjectFields([])
        setPrototypeNotice('Custom object saved.')
      }
    } finally {
      setObjectBusy(false)
    }
  }

  async function toggleCustomObject(object: CustomObject) {
    if (objectBusy) return
    setObjectBusy(true)
    try {
      const saved = await updateCustomObject(object.id, { active: !object.active })
      if (saved) setPrototypeNotice(`Custom object ${object.active ? 'paused' : 'activated'}.`)
    } finally {
      setObjectBusy(false)
    }
  }

  async function handleCreateProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = productDraft.name.trim()
    if (name.length < 1 || productBusy) return
    setProductBusy(true)
    try {
      const saved = await createProduct({
        name,
        code: productDraft.code.trim(),
        description: productDraft.description.trim(),
      })
      if (saved) {
        setProductDraft({ name: '', code: '', description: '' })
        setPrototypeNotice('Product saved.')
      }
    } finally {
      setProductBusy(false)
    }
  }

  async function toggleProduct(product: Product) {
    if (productBusy) return
    setProductBusy(true)
    try {
      const saved = await updateProduct(product.id, { active: !product.active })
      if (saved) setPrototypeNotice(`Product ${product.active ? 'paused' : 'activated'}.`)
    } finally {
      setProductBusy(false)
    }
  }

  function exportAnalyticsRollupsCsv() {
    if (typeof window === 'undefined') return
    const rollups = backendSnapshot?.analyticsRollups ?? backendSnapshot?.analytics_rollups ?? []
    const header = [
      'Period start',
      'Period end',
      'Open',
      'At risk',
      'Breached',
      'Active agents',
      'Avg occupancy',
      'Avg CSAT',
    ]
    const body = rollups.map((rollup) => [
      rollup.period_start,
      rollup.period_end,
      rollup.open_tickets,
      rollup.at_risk_tickets,
      rollup.breached_tickets,
      rollup.active_agents,
      rollup.avg_occupancy,
      rollup.avg_csat ?? '',
    ])
    const csv = [header, ...body]
      .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
      .join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `omni-analytics-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    announcePrototype(`Exported ${rollups.length} analytics rollup${rollups.length === 1 ? '' : 's'} to CSV.`)
  }

  async function handleCreateSavedReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = reportDraft.name.trim()
    if (name.length < 1 || reportBusy) return
    setReportBusy(true)
    try {
      const saved = await createSavedReport({ name, report_type: reportDraft.reportType })
      if (saved) {
        setReportDraft({ name: '', reportType: 'tickets' })
        setPrototypeNotice('Saved report created.')
      }
    } finally {
      setReportBusy(false)
    }
  }

  async function toggleSavedReport(report: SavedReport) {
    if (reportBusy) return
    setReportBusy(true)
    try {
      const saved = await updateSavedReport(report.id, { active: !report.active })
      if (saved) setPrototypeNotice(`Report ${report.active ? 'paused' : 'activated'}.`)
    } finally {
      setReportBusy(false)
    }
  }

  async function setSavedReportCadence(report: SavedReport, cadence: string) {
    if (reportBusy) return
    setReportBusy(true)
    try {
      await updateSavedReport(report.id, { cadence })
      setPrototypeNotice(cadence === 'none' ? 'Report unscheduled.' : `Report scheduled ${cadence}.`)
    } finally {
      setReportBusy(false)
    }
  }

  async function handleCreateServiceAppointment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const title = appointmentDraft.title.trim()
    if (title.length < 1 || !appointmentDraft.scheduledAt || appointmentBusy) return
    setAppointmentBusy(true)
    try {
      const saved = await createServiceAppointment({
        title,
        customer_id: appointmentDraft.customerId || undefined,
        technician_id: appointmentDraft.technicianId || undefined,
        scheduled_at: new Date(appointmentDraft.scheduledAt).toISOString(),
        duration_minutes: appointmentDraft.durationMinutes,
        location: appointmentDraft.location.trim() || undefined,
        notes: appointmentDraft.notes.trim() || undefined,
      })
      if (saved) {
        setAppointmentDraft({
          title: '',
          customerId: '',
          technicianId: '',
          scheduledAt: '',
          durationMinutes: 60,
          location: '',
          notes: '',
        })
        setPrototypeNotice('Service appointment scheduled.')
      }
    } finally {
      setAppointmentBusy(false)
    }
  }

  async function setAppointmentStatus(appointment: ServiceAppointment, status: string) {
    if (appointmentBusy || appointment.status === status) return
    setAppointmentBusy(true)
    try {
      const saved = await updateServiceAppointment(appointment.id, { status })
      if (saved) setPrototypeNotice(`Appointment marked ${status.replace(/_/g, ' ')}.`)
    } finally {
      setAppointmentBusy(false)
    }
  }

  async function reassignAppointmentTechnician(appointment: ServiceAppointment, technicianId: string) {
    if (appointmentBusy || appointment.technicianId === technicianId) return
    setAppointmentBusy(true)
    try {
      const saved = await updateServiceAppointment(appointment.id, { technician_id: technicianId })
      if (saved) setPrototypeNotice('Appointment reassigned.')
    } finally {
      setAppointmentBusy(false)
    }
  }

  async function handleCreateKnowledgeArticle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const title = articleDraft.title.trim()
    const body = articleDraft.body.trim()
    if (title.length < 1 || body.length < 1 || articleBusy) return
    const category = articleDraft.category.trim()
    setArticleBusy(true)
    try {
      const saved = await createKnowledgeArticle({
        title,
        body,
        status: articleDraft.status,
        language: articleDraft.language,
        tags: category ? [category] : [],
      })
      if (saved) {
        setArticleDraft({ title: '', category: '', status: 'draft', language: 'en', body: '' })
        setArticleFormOpen(false)
        setPrototypeNotice('Knowledge article created.')
      }
    } finally {
      setArticleBusy(false)
    }
  }

  async function setArticleStatus(article: KnowledgeArticle, status: KnowledgeArticle['status']) {
    if (articleBusy || article.status === status) return
    setArticleBusy(true)
    try {
      const saved = await updateKnowledgeArticle(article.id, { status })
      if (saved) setPrototypeNotice(`Article moved to ${status}.`)
    } finally {
      setArticleBusy(false)
    }
  }

  function parseTagList(value: string) {
    return value
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0)
  }

  async function handleCreateForumTopic(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const title = forumDraft.title.trim()
    if (title.length < 2 || forumBusy) return
    setForumBusy(true)
    try {
      const saved = await createDiscussionTopic({
        title,
        category: forumDraft.category.trim() || 'General',
        body: forumDraft.body.trim(),
      })
      if (saved) {
        setForumDraft({ title: '', category: '', body: '' })
        setForumOpen(false)
        setPrototypeNotice('Discussion topic created.')
      }
    } finally {
      setForumBusy(false)
    }
  }

  async function setForumTopicStatus(topic: DiscussionTopic, status: string) {
    if (forumBusy || topic.status === status) return
    setForumBusy(true)
    try {
      const saved = await updateDiscussionTopic(topic.id, { status })
      if (saved) setPrototypeNotice(`Topic marked ${status}.`)
    } finally {
      setForumBusy(false)
    }
  }

  async function toggleForumTopicPin(topic: DiscussionTopic) {
    if (forumBusy) return
    setForumBusy(true)
    try {
      const saved = await updateDiscussionTopic(topic.id, { pinned: !topic.pinned })
      if (saved) setPrototypeNotice(topic.pinned ? 'Topic unpinned.' : 'Topic pinned.')
    } finally {
      setForumBusy(false)
    }
  }

  async function toggleForumTopicComments(topic: DiscussionTopic) {
    if (expandedTopicId === topic.id) {
      setExpandedTopicId('')
      setTopicComments([])
      return
    }
    if (!backendSession) return
    setExpandedTopicId(topic.id)
    setTopicComments([])
    setCommentDraft('')
    setTopicCommentsBusy(true)
    try {
      const comments = await fetchBackendDiscussionComments(topic.id, backendSession)
      setTopicComments(comments)
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Could not load comments.')
    } finally {
      setTopicCommentsBusy(false)
    }
  }

  async function handleAddForumComment(event: FormEvent<HTMLFormElement>, topic: DiscussionTopic) {
    event.preventDefault()
    const body = commentDraft.trim()
    if (body.length < 1 || topicCommentsBusy || !backendSession) return
    setTopicCommentsBusy(true)
    try {
      await createBackendDiscussionComment(topic.id, { body }, backendSession)
      const comments = await fetchBackendDiscussionComments(topic.id, backendSession)
      setTopicComments(comments)
      setCommentDraft('')
      setPrototypeNotice('Reply posted.')
      await refreshBackend()
    } catch (error) {
      setPrototypeNotice(error instanceof Error ? error.message : 'Reply failed.')
    } finally {
      setTopicCommentsBusy(false)
    }
  }

  async function handleCreateCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = customerDraft.name.trim()
    const email = customerDraft.email.trim()
    if (name.length < 1 || email.length < 3 || customerBusy) return
    setCustomerBusy(true)
    try {
      const saved = await createCustomer({
        name,
        email,
        company_id: customerDraft.companyId || null,
        location: customerDraft.location.trim(),
        tags: parseTagList(customerDraft.tags),
        notes: customerDraft.notes.trim(),
      })
      if (saved) {
        setCustomerDraft({ name: '', email: '', companyId: '', location: '', tags: '', notes: '' })
        setCustomerFormOpen(false)
        setPrototypeNotice('Customer created.')
      }
    } finally {
      setCustomerBusy(false)
    }
  }

  function openCustomerEditor() {
    setCustomerEdit({
      name: selectedCustomer.name,
      email: selectedCustomer.email,
      location: selectedCustomer.location === 'Market workspace' ? '' : selectedCustomer.location,
      sentiment:
        selectedCustomer.csat >= 4.5
          ? 'positive'
          : selectedCustomer.csat >= 4
            ? 'neutral'
            : 'frustrated',
      tags: selectedCustomer.tags.join(', '),
      notes: '',
    })
    setCustomerEditOpen(true)
  }

  async function handleUpdateCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = customerEdit.name.trim()
    const email = customerEdit.email.trim()
    if (name.length < 1 || email.length < 3 || customerBusy) return
    setCustomerBusy(true)
    try {
      const saved = await updateCustomer(selectedCustomer.id, {
        name,
        email,
        location: customerEdit.location.trim(),
        sentiment: customerEdit.sentiment,
        tags: parseTagList(customerEdit.tags),
        ...(customerEdit.notes.trim() ? { notes: customerEdit.notes.trim() } : {}),
      })
      if (saved) {
        setCustomerEditOpen(false)
        setPrototypeNotice('Customer profile updated.')
      }
    } finally {
      setCustomerBusy(false)
    }
  }

  function openSetupModule(moduleName: string) {
    // Some catalog tiles live on a dedicated screen — navigate there directly.
    const screenRoutes: Record<string, ScreenId> = {
      'Field service scheduling': 'workforce',
      'Scheduled exports': 'analytics',
      Threads: 'inbox',
      Omnichat: 'channels',
    }
    if (screenRoutes[moduleName]) {
      if (moduleName === 'Scheduled exports') setAnalyticsReportGroup('scheduled')
      selectScreen(screenRoutes[moduleName])
      return
    }
    const panelId = setupToolPanel[moduleName]
    if (!panelId) {
      setSetupModuleHint(`${moduleName} settings are managed elsewhere.`)
      return
    }
    // Route the right Setup section + People sub-view for the panel that hosts this tool.
    setSetupSection(setupPanelSection[panelId] ?? setupSection)
    const peopleRoutes: Record<string, 'users' | 'groups' | 'security' | 'hours'> = {
      Agents: 'users',
      'Market access': 'users',
      Groups: 'groups',
      'Business hours': 'hours',
      Roles: 'security',
      'Permission profiles': 'security',
      MFA: 'security',
      'Enterprise SSO': 'security',
      'API status': 'security',
      'Profile settings': 'security',
      'Security controls': 'security',
    }
    if (peopleRoutes[moduleName]) {
      setPeopleView(peopleRoutes[moduleName])
    }
    if (moduleName === 'Contact fields') setCustomFieldEntity('contact')
    if (moduleName === 'Company fields') setCustomFieldEntity('company')
    setActiveSetupTool(moduleName)
    setSetupModuleHint('')
    if (typeof document !== 'undefined') {
      window.requestAnimationFrame(() => {
        document.getElementById('setup-screen-top')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    }
  }

  function closeSetupTool() {
    setActiveSetupTool(null)
    setSetupModuleHint('')
  }

  async function mergeDuplicateTicket(suggestion: DuplicateTicketSuggestion) {
    if (!backendSession) {
      announcePrototype('Backend login is required before merging tickets.')
      return
    }
    const confirmed = window.confirm(
      `Merge ${suggestion.ticketNumber} into ${selectedConversation.ticketNumber}? The source ticket will close and keep an audit note.`,
    )
    if (!confirmed) return
    setMergeTicketBusy(suggestion.ticketId)
    try {
      await mergeBackendTickets(
        selectedConversation.id,
        {
          source_ticket_id: suggestion.ticketId,
          reason: `Operator confirmed duplicate from ${selectedConversation.ticketNumber}.`,
          actor: backendSession.user.email,
          close_source: true,
        },
        backendSession,
      )
      await refreshBackend()
      announcePrototype(`${suggestion.ticketNumber} merged into ${selectedConversation.ticketNumber}.`)
    } catch (error) {
      announcePrototype(`Merge failed: ${error instanceof Error ? error.message : 'backend request failed'}`)
    } finally {
      setMergeTicketBusy('')
    }
  }

  // Group a related ticket with the current one into a case (instead of merging).
  // Attaches to whichever case already exists, or creates a fresh case from both.
  async function linkSuggestionIntoCase(suggestion: DuplicateTicketSuggestion) {
    if (!backendSession) {
      announcePrototype('Backend login is required before linking a case.')
      return
    }
    const suggestionConversation = state.conversations.find((conv) => conv.id === suggestion.ticketId)
    setCaseLinkBusy(suggestion.ticketId)
    try {
      if (selectedConversation.caseId) {
        await attachCaseTicket(selectedConversation.caseId, suggestion.ticketId)
        announcePrototype(`${suggestion.ticketNumber} added to this case.`)
      } else if (suggestionConversation?.caseId) {
        await attachCaseTicket(suggestionConversation.caseId, selectedConversation.id)
        announcePrototype(`${selectedConversation.ticketNumber} added to ${suggestion.ticketNumber}'s case.`)
      } else {
        await createCase({
          customerId: selectedConversation.customerId,
          title: selectedConversation.subject,
          ticketIds: [selectedConversation.id, suggestion.ticketId],
        })
        announcePrototype(`Grouped ${selectedConversation.ticketNumber} and ${suggestion.ticketNumber} into a case.`)
      }
    } finally {
      setCaseLinkBusy('')
    }
  }

  function ticketFieldsForChannel(channelId: ChannelId) {
    return state.ticketFields
      .filter((field) => field.active && (field.channels.length === 0 || field.channels.includes(channelId)))
      .sort((a, b) => a.position - b.position || a.label.localeCompare(b.label))
  }

  function customFieldIsMissing(field: TicketField, value: unknown) {
    if (field.fieldType === 'checkbox') return value !== true
    return value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0)
  }

  function normalizeTicketFieldKey(value: string) {
    return value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .replace(/^[^a-z]+/, '')
      .slice(0, 64)
  }

  function ticketFieldOptions(value: string) {
    const seen = new Set<string>()
    return value
      .split(',')
      .map((option) => option.trim())
      .filter((option) => {
        const key = option.toLowerCase()
        if (!option || seen.has(key)) return false
        seen.add(key)
        return true
      })
  }

  function updateQuickCustomField(field: TicketField, value: unknown) {
    setQuickTicket((current) => ({
      ...current,
      customFields: {
        ...(current.customFields ?? {}),
        [field.key]: value,
      },
    }))
  }

  function updateConversationCustomField(field: TicketField, value: unknown) {
    updateConversation(selectedConversation.id, {
      customFields: {
        ...selectedConversation.customFields,
        [field.key]: value,
      },
    })
  }

  function renderTicketFieldInput(
    field: TicketField,
    value: unknown,
    onChange: (value: unknown) => void,
  ) {
    const id = `field-${field.id}`
    if (field.fieldType === 'select') {
      return (
        <select id={id} value={typeof value === 'string' ? value : ''} onChange={(event) => onChange(event.target.value)}>
          <option value="">Not set</option>
          {field.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      )
    }
    if (field.fieldType === 'multiselect') {
      const currentValues = Array.isArray(value) ? value.map(String) : []
      return (
        <div className="custom-field-options" id={id}>
          {field.options.map((option) => (
            <label key={option}>
              <input
                type="checkbox"
                checked={currentValues.includes(option)}
                onChange={(event) => {
                  onChange(
                    event.target.checked
                      ? [...currentValues, option]
                      : currentValues.filter((item) => item !== option),
                  )
                }}
              />
              {option}
            </label>
          ))}
        </div>
      )
    }
    if (field.fieldType === 'checkbox') {
      return (
        <label className="custom-field-check" htmlFor={id}>
          <input id={id} type="checkbox" checked={value === true} onChange={(event) => onChange(event.target.checked)} />
          <span>{field.placeholder || field.helpText || 'Enabled'}</span>
        </label>
      )
    }
    if (field.fieldType === 'textarea') {
      return (
        <textarea
          id={id}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => onChange(event.target.value)}
          placeholder={field.placeholder}
        />
      )
    }
    return (
      <input
        id={id}
        type={field.fieldType === 'number' ? 'number' : field.fieldType === 'date' ? 'date' : 'text'}
        value={value === undefined || value === null ? '' : String(value)}
        onChange={(event) => {
          if (field.fieldType === 'number') {
            onChange(event.target.value === '' ? '' : Number(event.target.value))
            return
          }
          onChange(event.target.value)
        }}
        placeholder={field.placeholder}
      />
    )
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
    const missingRequiredField = ticketFieldsForChannel(quickTicket.channelId).find((field) =>
      field.required && customFieldIsMissing(field, quickTicket.customFields?.[field.key]),
    )
    if (missingRequiredField) {
      announcePrototype(`${missingRequiredField.label} is required before creating this ticket.`)
      return
    }
    createConversation(quickTicket)
    setQuickCreateOpen(false)
    setQuickTicket((current) => ({ ...current, subject: '', body: '', customFields: {} }))
    announcePrototype('New ticket created and opened in the Work Queue.')
  }

  function toggleNav() {
    setNavExpanded((value) => {
      const next = !value
      try {
        window.localStorage.setItem('omni-nav-expanded', String(next))
      } catch {
        /* ignore storage failures */
      }
      return next
    })
  }

  function openConversation(conversation: OmniConversation) {
    setComposerChannel(conversation.channelId)
    setComposerText('')
    selectConversation(conversation.id)
    setTicketDetailOpen(true)
  }

  function openConversationInInbox(conversation: OmniConversation) {
    openConversation(conversation)
    selectScreen('inbox')
  }

  function resetInboxListControls() {
    setInboxGroup('all')
    setInboxCreated('all')
    setInboxDue('any')
    setInboxPage(0)
  }

  function openWorkQueueFocus(
    filters: Partial<typeof state.filters>,
    conversation?: OmniConversation,
    due?: 'today' | 'overdue',
    viewId = 'all-open',
  ) {
    setInboxView(viewId)
    resetFilters()
    resetInboxListControls()
    if (Object.keys(filters).length > 0) setFilters(filters)
    if (due) setInboxDue(due)
    if (conversation) {
      openConversationInInbox(conversation)
      return
    }
    selectScreen('inbox')
  }

  function applyInboxView(viewId: string) {
    setInboxView(viewId)
    resetFilters()
    resetInboxListControls()
    if (viewId === 'my-open') setFilters({ assignee: selectedAgent?.id ?? 'all' })
    if (viewId === 'overdue') setFilters({ sla: 'breached' })
    if (viewId === 'ai-escalations') setFilters({ sentiment: 'at-risk' })
    if (viewId === 'whatsapp') setFilters({ channel: 'whatsapp' })
  }

  function focusComposer() {
    if (typeof document === 'undefined') return
    window.requestAnimationFrame(() => {
      const input = document.getElementById('ticket-composer-input') as HTMLTextAreaElement | null
      input?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      input?.focus()
    })
  }

  function handleTicketAction(actionId: (typeof freshdeskTicketActionItems)[number]['id']) {
    if (actionId === 'reply') {
      setComposerMode('reply')
      focusComposer()
      announcePrototype('Reply composer ready.')
      return
    }
    if (actionId === 'note') {
      setComposerMode('note')
      focusComposer()
      announcePrototype('Private note composer ready.')
      return
    }
    if (actionId === 'forward') {
      setComposerMode('handoff')
      focusComposer()
      announcePrototype('Forward/handoff composer ready with full case context.')
      return
    }
    if (actionId === 'child') {
      // Distinct from Forward (which opens the team-handoff composer): Child task
      // opens the create-ticket panel pre-filled from this case so a linked child
      // ticket can be raised.
      openQuickCreate(selectedConversation.channelId)
      announcePrototype('Child ticket draft opened.')
      return
    }
    if (actionId === 'close-silent') {
      updateConversation(selectedConversation.id, { status: 'resolved', slaState: 'healthy' })
      announcePrototype('Ticket closed without a customer notification email.')
      return
    }
    // watch: toggle this operator's watch on the ticket (persisted per user)
    const ticketId = selectedConversation.id
    const watching = watchedTicketIds.includes(ticketId)
    setWatchedTicketIds((current) =>
      watching ? current.filter((id) => id !== ticketId) : [...current, ticketId],
    )
    announcePrototype(
      watching
        ? `Stopped watching ${selectedConversation.ticketNumber}.`
        : `You are now watching ${selectedConversation.ticketNumber}.`,
    )
  }

  function openDirectChannel(channelId: ChannelId) {
    setLiveChatDraft('')
    setSelectedChannel(channelId)
  }

  function defaultAttachmentDraft(channelId: ChannelId): AttachmentDraft {
    if (channelId === 'email') {
      return {
        filename: 'customer-email-thread.pdf',
        contentType: 'application/pdf',
        sizeBytes: 380_000,
      }
    }
    if (channelId === 'whatsapp' || channelId === 'instagram' || channelId === 'facebook') {
      return {
        filename: 'customer-chat-screenshot.png',
        contentType: 'image/png',
        sizeBytes: 248_000,
      }
    }
    return {
      filename: 'customer-context-note.txt',
      contentType: 'text/plain',
      sizeBytes: 24_000,
    }
  }

  function updateAttachmentDraft(patch: Partial<AttachmentDraft>) {
    setAttachmentDraft((current) => ({
      ...(current ?? defaultAttachmentDraft(composerChannel)),
      ...patch,
    }))
  }

  function insertResponseMacro(macroId: string) {
    const suggestion = composerMacroOptions.find((item) => item.macro.id === macroId)
    if (!suggestion) return
    setComposerText(suggestion.macro.body)
    recordResponseMacroUse(suggestion.macro.id, selectedConversation.id)
  }

  function sendComposer() {
    submitComposer({
      conversationId: selectedConversation.id,
      mode: composerMode,
      channelId: composerChannel,
      body: composerText,
      online,
      handoffTeam: effectiveHandoffTeam,
      handoffReason,
      attachment: attachmentDraft ?? undefined,
    })
    setComposerText('')
    setAttachmentDraft(null)
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
        onClick={(event) =>
          handleAppLink(event, () => {
            if (item.id === 'inbox') setTicketDetailOpen(false)
            selectScreen(item.id)
          })
        }
        title={item.label}
        aria-label={item.label}
        aria-current={active ? 'page' : undefined}
      >
        <Icon size={18} />
        <span>{item.label}</span>
      </a>
    )
  }

  function renderFreshworksDashboardMirror() {
    const groupOptions = state.supportGroups.map((group) => group.name)
    const isUnfilteredDashboard =
      dashboardRange === 'all' && dashboardTicketGroup === 'all' && dashboardChatGroup === 'all'
    const endpointDashboard = backendSession
      ? dashboardAnalytics ?? (isUnfilteredDashboard ? backendSnapshot?.analytics : null)
      : null
    const ticketTrends = endpointDashboard?.ticket_trends ?? {}
    const ticketPerformance = endpointDashboard?.ticket_performance ?? {}
    const ticketCsat = endpointDashboard?.ticket_csat ?? {}
    const chatTrends = endpointDashboard?.chat_trends ?? {}
    const chatPerformance = endpointDashboard?.chat_performance ?? {}
    const chatCsat = endpointDashboard?.chat_csat ?? {}
    const agentAvailability = endpointDashboard?.agent_availability ?? {}
    const recentActivity = endpointDashboard?.recent_activity ?? []

    const ticketTrendRows = [
      { label: 'Open', value: ticketTrends.open ?? 0, action: () => openWorkQueueFocus({}, undefined, undefined, 'all-open') },
      { label: 'Unassigned', value: ticketTrends.unassigned ?? 0, action: () => openWorkQueueFocus({}, undefined, undefined, 'unassigned') },
      { label: 'Overdue', value: ticketTrends.overdue ?? 0, action: () => openWorkQueueFocus({ sla: 'breached' }, undefined, undefined, 'overdue') },
      { label: 'Due today', value: ticketTrends.due_today ?? 0, action: () => openWorkQueueFocus({}, undefined, 'today', 'all-open') },
    ]
    const chatTrendRows: { label: string; value: number; action: () => void }[] = [
      {
        label: 'Unassigned chats',
        value: chatTrends.unassigned ?? 0,
        action: () => openWorkQueueFocus({ status: 'new' }),
      },
      {
        label: 'Assigned not replied',
        value: chatTrends.assigned_not_replied ?? 0,
        action: () => openWorkQueueFocus({ status: 'open' }),
      },
      {
        label: 'Assigned chats',
        value: chatTrends.assigned ?? 0,
        action: () => openWorkQueueFocus({ status: 'pending' }),
      },
    ]
    const chatPerformanceRows: [string, string][] = [
      ['Average first response time', formatDuration(chatPerformance.first_response_seconds ?? null)],
      ['Average response time', formatDuration(chatPerformance.response_seconds ?? null)],
      ['Average resolution time', formatDuration(chatPerformance.resolution_seconds ?? null)],
      ['Average wait time', formatDuration(chatPerformance.wait_seconds ?? null)],
    ]
    const ticketCsatRows: [string, number, string][] = [
      ['Negative', ticketCsat.negative_pct ?? 0, 'bad'],
      ['Neutral', ticketCsat.neutral_pct ?? 0, 'neutral'],
      ['Positive', ticketCsat.positive_pct ?? 0, 'good'],
    ]
    const ticketAvgFirstResponse = formatDuration(ticketPerformance.avg_first_response_seconds ?? null)
    const ticketResolutionWithinSla =
      ticketPerformance.resolution_within_sla_pct == null
        ? '—'
        : `${Math.round(ticketPerformance.resolution_within_sla_pct)}%`
    const chatAvgRating =
      chatCsat.avg_rating == null ? '—' : `${Math.round(chatCsat.avg_rating * 10) / 10}/5`
    const chatStars = chatCsat.avg_rating == null ? 0 : Math.round(chatCsat.avg_rating)

    return (
      <section className="omni-desk-dashboard" aria-label="Omnichannel Dashboard">
        <div className="desk-filter-strip">
          <label className="desk-range-filter">
            <Clock size={15} />
            <span>Period:</span>
            <select
              value={dashboardRange}
              onChange={(event) => setDashboardRange(event.target.value as DashboardRange)}
              aria-label="Dashboard period"
            >
              {DASHBOARD_RANGES.map((range) => (
                <option key={range.id} value={range.id}>
                  {range.label}
                </option>
              ))}
            </select>
          </label>
          <span className="desk-filter-divider" />
          <label>
            <span>Ticket groups:</span>
            <select value={dashboardTicketGroup} onChange={(event) => setDashboardTicketGroup(event.target.value)}>
              <option value="all">All ticket groups</option>
              {groupOptions.map((group) => (
                <option key={group} value={group}>
                  {group}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Chat groups:</span>
            <select value={dashboardChatGroup} onChange={(event) => setDashboardChatGroup(event.target.value)}>
              <option value="all">All chat groups</option>
              {groupOptions.map((group) => (
                <option key={group} value={group}>
                  {group}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="desk-dashboard-grid">
          {dashboardAnalyticsError && (
            <div className="desk-dashboard-sync-note">
              {dashboardAnalyticsError}
            </div>
          )}
          <article className="desk-widget">
            <header>
              <span>Ticket trends</span>
            </header>
            <div className="desk-trend-list">
              {ticketTrendRows.map((row) => (
                <button type="button" key={row.label} onClick={row.action}>
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                </button>
              ))}
            </div>
          </article>

          <article className="desk-widget">
            <header>
              <span>Ticket performance</span>
            </header>
            <div className="desk-performance-two">
              <div>
                <span>Average First Response Time</span>
                <strong>{ticketAvgFirstResponse}</strong>
              </div>
              <div>
                <span>Resolution within SLA</span>
                <strong>{ticketResolutionWithinSla}</strong>
              </div>
            </div>
          </article>

          <article className="desk-widget">
            <header>
              <span>Ticket - CSAT scores</span>
            </header>
            <div className="desk-csat-grid">
              <div>
                <span>Responses received</span>
                <strong>{ticketCsat.responses ?? 0}</strong>
              </div>
              {ticketCsatRows.map(([label, value, tone]) => (
                <div className={`desk-csat-score ${tone}`} key={label}>
                  <span>{label}</span>
                  <strong>{value}%</strong>
                  <b />
                </div>
              ))}
            </div>
          </article>

          <article className="desk-widget">
            <header>
              <span>Chat trends</span>
            </header>
            <p className="desk-widget-note">Conversations unassigned or assigned and not replied for 15 mins</p>
            <div className="desk-trend-list">
              {chatTrendRows.map((row) => (
                <button type="button" key={row.label} onClick={row.action}>
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                </button>
              ))}
            </div>
          </article>

          <article className="desk-widget">
            <header>
              <span>Chat performance</span>
            </header>
            <div className="desk-kpi-list">
              {chatPerformanceRows.map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </article>

          <article className="desk-widget">
            <header>
              <span>Chat - CSAT scores</span>
            </header>
            <div className="desk-chat-csat">
              <div
                className="desk-star-row"
                aria-label={`Average chat rating ${chatAvgRating}`}
              >
                {Array.from({ length: 5 }, (_, index) => (
                  <Star
                    size={24}
                    fill={index < chatStars ? 'currentColor' : 'none'}
                    key={index}
                  />
                ))}
                <strong>{chatAvgRating}</strong>
              </div>
              <span>Average rating based on all satisfactory interactions</span>
              <div className="desk-progress-row good">
                <span>Yes</span>
                <b><i style={{ width: `${chatCsat.yes_pct ?? 0}%` }} /></b>
                <strong>{chatCsat.yes_pct ?? 0}% ({chatCsat.yes_count ?? 0})</strong>
              </div>
              <div className="desk-progress-row bad">
                <span>No</span>
                <b><i style={{ width: `${chatCsat.no_pct ?? 0}%` }} /></b>
                <strong>{chatCsat.no_pct ?? 0}% ({chatCsat.no_count ?? 0})</strong>
              </div>
            </div>
          </article>

          <article className="desk-widget desk-small-widget">
            <header>
              <span>Available agents</span>
              <a href={routeHref({ screen: 'workforce' })} onClick={(event) => handleAppLink(event, () => selectScreen('workforce'))}>
                View details
              </a>
            </header>
            <div className="desk-agent-counts">
              <div><Users size={18} /><span>Agents on Tickets</span><strong>{agentAvailability.agents_on_tickets ?? 0}</strong></div>
              <div><MessageCircle size={18} /><span>Agents on Chat</span><strong>{agentAvailability.agents_on_chat ?? 0}</strong></div>
            </div>
          </article>

          <article className="desk-widget desk-small-widget">
            <header>
              <span>To-do</span>
            </header>
            <form
              className="desk-todo-box"
              onSubmit={(event) => {
                event.preventDefault()
                addTodo()
              }}
            >
              <button type="submit" aria-label="Add to-do">
                <Plus size={14} />
              </button>
              <input
                aria-label="Add a to-do"
                placeholder="Add a to-do"
                value={todoDraft}
                onChange={(event) => setTodoDraft(event.target.value)}
              />
            </form>
            {todos.length === 0 ? (
              <span className="desk-todo-empty">You have no tasks to do!</span>
            ) : (
              <ul className="desk-todo-list">
                {todos.map((todo) => (
                  <li key={todo.id} className={todo.done ? 'done' : ''}>
                    <label>
                      <input type="checkbox" checked={todo.done} onChange={() => toggleTodo(todo.id)} />
                      <span>{todo.label}</span>
                    </label>
                    <button type="button" aria-label="Remove to-do" onClick={() => removeTodo(todo.id)}>
                      <X size={13} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="desk-widget desk-activity-widget">
            <header>
              <span>Recent activity</span>
              <button
                type="button"
                className="desk-icon-button"
                onClick={() => refreshBackend()}
                aria-label="Refresh recent activity"
                title="Refresh"
              >
                <RefreshCw size={14} />
              </button>
            </header>
            {recentActivity.length === 0 ? (
              <span className="desk-todo-empty">No recent activity in this period.</span>
            ) : (
              <ul className="desk-activity-list">
                {recentActivity.map((item) => {
                  const conversation = state.conversations.find((entry) => entry.id === item.ticket_id)
                  return (
                    <li key={item.id}>
                      <a
                        href={routeHref({ screen: 'inbox' })}
                        onClick={(event) =>
                          handleAppLink(event, () => {
                            if (conversation) openConversationInInbox(conversation)
                          })
                        }
                      >
                        <div className="desk-activity-head">
                          <strong>{item.public_id}</strong>
                          <span>{titleCase(item.type)} · {item.actor}</span>
                        </div>
                        <em>{item.body}</em>
                        <small>{formatTime(item.created_at)}</small>
                      </a>
                    </li>
                  )
                })}
              </ul>
            )}
          </article>
        </div>
      </section>
    )
  }

  function renderCommand() {
    return (
      <div className="screen-stack command-freshdesk-only">
        {renderFreshworksDashboardMirror()}
      </div>
    )
  }

  function renderFilters() {
    const inboxViewGroups = [
      {
        title: 'Default views',
        views: [
          { id: 'all-open', label: 'All open tickets', count: state.conversations.filter((item) => item.status !== 'resolved').length },
          { id: 'my-open', label: 'My open tickets', count: state.conversations.filter((item) => item.assigneeId === selectedAgent?.id && item.status !== 'resolved').length },
          { id: 'unassigned', label: 'Unassigned', count: state.conversations.filter((item) => item.status === 'new').length },
          { id: 'overdue', label: 'Overdue', count: state.conversations.filter((item) => item.slaState === 'breached').length },
        ],
      },
      {
        title: 'Shared views',
        views: [
          { id: 'whatsapp', label: 'WhatsApp queues', count: state.conversations.filter((item) => item.channelId === 'whatsapp').length },
          { id: 'ai-escalations', label: 'AI escalations', count: state.conversations.filter((item) => item.sentiment === 'at-risk').length },
          { id: 'resolved', label: 'Resolved today', count: state.conversations.filter((item) => item.status === 'resolved').length },
        ],
      },
    ]

    return (
      <aside className="filter-panel">
        <div className="panel-head compact">
          <div>
            <span>Focus</span>
            <h2>Work Queue</h2>
          </div>
          <Filter size={18} />
        </div>

        <div className="freshdesk-view-rail" aria-label="Ticket views">
          <div className="view-rail-head">
            <strong>Ticket views</strong>
          </div>
          {inboxViewGroups.map((group) => (
            <div className="view-group" key={group.title}>
              <span>{group.title}</span>
              {group.views.map((view) => (
                <button
                  type="button"
                  key={view.id}
                  className={inboxView === view.id ? 'active' : ''}
                  aria-pressed={inboxView === view.id}
                  onClick={() => applyInboxView(view.id)}
                >
                  <small>{view.label}</small>
                  <strong>{view.count}</strong>
                </button>
              ))}
            </div>
          ))}
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
          <button
            type="button"
            className="customer-edit-toggle"
            aria-expanded={customerEditOpen}
            onClick={() => (customerEditOpen ? setCustomerEditOpen(false) : openCustomerEditor())}
          >
            <Settings size={14} />
            {customerEditOpen ? 'Close' : 'Edit'}
          </button>
        </div>
        {customerEditOpen ? (
          <form className="customer-edit-form" onSubmit={handleUpdateCustomer}>
            <label>
              <span>Name</span>
              <input
                required
                value={customerEdit.name}
                onChange={(event) => setCustomerEdit((current) => ({ ...current, name: event.target.value }))}
                disabled={customerBusy}
              />
            </label>
            <label>
              <span>Email</span>
              <input
                required
                type="email"
                value={customerEdit.email}
                onChange={(event) => setCustomerEdit((current) => ({ ...current, email: event.target.value }))}
                disabled={customerBusy}
              />
            </label>
            <label>
              <span>Location</span>
              <input
                value={customerEdit.location}
                onChange={(event) => setCustomerEdit((current) => ({ ...current, location: event.target.value }))}
                disabled={customerBusy}
              />
            </label>
            <label>
              <span>Sentiment</span>
              <select
                value={customerEdit.sentiment}
                onChange={(event) =>
                  setCustomerEdit((current) => ({
                    ...current,
                    sentiment: event.target.value as BackendCustomer['sentiment'],
                  }))
                }
                disabled={customerBusy}
              >
                {(['positive', 'neutral', 'frustrated', 'angry'] as const).map((sentiment) => (
                  <option key={sentiment} value={sentiment}>
                    {titleCase(sentiment)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Tags (comma separated)</span>
              <input
                value={customerEdit.tags}
                onChange={(event) => setCustomerEdit((current) => ({ ...current, tags: event.target.value }))}
                disabled={customerBusy}
              />
            </label>
            <label>
              <span>Add note</span>
              <textarea
                rows={2}
                value={customerEdit.notes}
                onChange={(event) => setCustomerEdit((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Optional: replace the stored note."
                disabled={customerBusy}
              />
            </label>
            <button type="submit" className="primary-action" disabled={customerBusy}>
              Save changes
            </button>
          </form>
        ) : null}
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
    const attachmentEvents = selectedConversation.timeline.filter(
      (event) => event.type === 'automation' && event.body.toLowerCase().includes('attachment'),
    )
    const selectedTicketFields = ticketFieldsForChannel(selectedConversation.channelId)
    const duplicateSuggestions = selectedConversation.copilot.duplicateSuggestions ?? []

    // ── Context-tab data (B-111): real content, no placeholder text ──────────
    const threadEvents = selectedConversation.timeline.filter((event) => event.authorRole !== 'system')
    const linkedItems: { key: string; ticketNumber: string; label: string; onOpen: () => void }[] = [
      ...selectedHandoffs.map((handoff) => {
        const linked = handoff.linkedConversationId
          ? state.conversations.find((conversation) => conversation.id === handoff.linkedConversationId)
          : undefined
        return {
          key: `handoff-${handoff.id}`,
          ticketNumber: linked?.ticketNumber ?? handoff.ticketNumber,
          label: `Handoff → ${handoff.receivingTeam}`,
          onOpen: () => (linked ? openConversationInInbox(linked) : selectScreen('handoffs')),
        }
      }),
      ...duplicateSuggestions.map((dup) => ({
        key: `dup-${dup.ticketId}`,
        ticketNumber: dup.ticketNumber,
        label: 'Possible duplicate',
        onOpen: () => {
          const conversation = state.conversations.find((entry) => entry.id === dup.ticketId)
          if (conversation) openConversationInInbox(conversation)
        },
      })),
    ]
    const resolvedDurations = state.conversations
      .map((conversation) => resolutionSeconds(conversation))
      .filter((value): value is number => value != null)
    const ahtLabel = formatDuration(
      resolvedDurations.length
        ? resolvedDurations.reduce((total, value) => total + value, 0) / resolvedDurations.length
        : null,
    )
    const ticketTimeLogs = timeLogs[selectedConversation.id] ?? []
    const totalLoggedMinutes = ticketTimeLogs.reduce((total, log) => total + log.minutes, 0)

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

        <div className="ticket-action-bar" aria-label="Ticket actions">
          {freshdeskTicketActionItems.map(({ id, label, shortcut, icon: ActionIcon }) => {
            const watching = id === 'watch' && watchedTicketIds.includes(selectedConversation.id)
            const modeActive =
              (id === 'reply' && composerMode === 'reply') ||
              (id === 'note' && composerMode === 'note') ||
              (id === 'forward' && composerMode === 'handoff')
            const isActive = watching || modeActive
            return (
              <button
                type="button"
                key={id}
                className={isActive ? 'active' : ''}
                aria-pressed={
                  id === 'watch'
                    ? watching
                    : id === 'reply' || id === 'note' || id === 'forward'
                      ? modeActive
                      : undefined
                }
                onClick={() => handleTicketAction(id)}
              >
                <ActionIcon size={15} />
                <span>{id === 'watch' && watching ? 'Watching' : label}</span>
                {shortcut ? <kbd>{shortcut}</kbd> : null}
              </button>
            )
          })}
          <button type="button" onClick={() => setGlobalSearchOpen(true)}>
            <Search size={15} />
            <span>Jump</span>
            <kbd>j/k</kbd>
          </button>
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

        <div className="ticket-context-shell">
          <div className="ticket-context-tabs" role="tablist" aria-label="Ticket context">
            {[
              { id: 'activities' as TicketDetailTab, label: 'Activities', count: selectedConversation.timeline.length },
              { id: 'threads' as TicketDetailTab, label: 'Threads', count: selectedConversation.timeline.filter((event) => event.authorRole !== 'system').length },
              { id: 'linked' as TicketDetailTab, label: 'Linked tickets', count: linkedItems.length },
              { id: 'time' as TicketDetailTab, label: 'Time logs', count: ticketTimeLogs.length },
            ].map((tab) => (
              <button
                type="button"
                key={tab.id}
                role="tab"
                aria-selected={ticketDetailTab === tab.id}
                className={ticketDetailTab === tab.id ? 'active' : ''}
                onClick={() => setTicketDetailTab(tab.id)}
              >
                {tab.label}
                <span>{tab.count}</span>
              </button>
            ))}
          </div>
          <div className="ticket-context-panel">
            {ticketDetailTab === 'activities' ? (
              <ul className="ticket-context-list">
                {selectedConversation.timeline.length === 0 ? (
                  <li className="muted">No activity yet.</li>
                ) : (
                  [...selectedConversation.timeline]
                    .reverse()
                    .slice(0, 6)
                    .map((event) => (
                      <li key={event.id}>
                        <strong>{event.author}</strong>
                        <span>{titleCase(event.type)}</span>
                        <small>{formatTime(event.timestamp)}</small>
                      </li>
                    ))
                )}
              </ul>
            ) : null}
            {ticketDetailTab === 'threads' ? (
              <ul className="ticket-context-list">
                {threadEvents.length === 0 ? (
                  <li className="muted">No replies or notes yet.</li>
                ) : (
                  threadEvents.map((event) => (
                    <li key={event.id}>
                      <strong>{event.author}</strong>
                      <span>
                        {event.authorRole === 'customer'
                          ? 'Customer'
                          : event.type === 'internal-note'
                            ? 'Note'
                            : 'Reply'}
                      </span>
                      <em>{event.body.slice(0, 90)}</em>
                    </li>
                  ))
                )}
              </ul>
            ) : null}
            {ticketDetailTab === 'linked' ? (
              <ul className="ticket-context-list">
                {linkedItems.length === 0 ? (
                  <li className="muted">No linked tickets.</li>
                ) : (
                  linkedItems.map((item) => (
                    <li key={item.key}>
                      <button type="button" className="ticket-context-link" onClick={item.onOpen}>
                        <strong>{item.ticketNumber}</strong>
                        <span>{item.label}</span>
                      </button>
                    </li>
                  ))
                )}
              </ul>
            ) : null}
            {ticketDetailTab === 'time' ? (
              <div className="ticket-time-logs">
                <div className="ticket-time-summary">
                  <div>
                    <span>Avg handling time</span>
                    <strong>{ahtLabel}</strong>
                  </div>
                  <div>
                    <span>Logged on this ticket</span>
                    <strong>{totalLoggedMinutes}m</strong>
                  </div>
                </div>
                <form
                  className="ticket-time-form"
                  onSubmit={(event) => {
                    event.preventDefault()
                    addTimeLog(selectedConversation.id)
                  }}
                >
                  <input
                    type="number"
                    min="1"
                    placeholder="Minutes"
                    value={timeLogDraft}
                    onChange={(event) => setTimeLogDraft(event.target.value)}
                    aria-label="Minutes spent on this ticket"
                  />
                  <button type="submit">Log time</button>
                </form>
                <ul className="ticket-context-list">
                  {ticketTimeLogs.length === 0 ? (
                    <li className="muted">No time logged yet.</li>
                  ) : (
                    ticketTimeLogs.map((log) => (
                      <li key={log.id}>
                        <strong>{log.minutes}m</strong>
                        <span>{log.agent}</span>
                        <small>{formatTime(log.at)}</small>
                        <button
                          type="button"
                          aria-label="Remove time log"
                          className="ticket-time-remove"
                          onClick={() => removeTimeLog(selectedConversation.id, log.id)}
                        >
                          <X size={12} />
                        </button>
                      </li>
                    ))
                  )}
                </ul>
              </div>
            ) : null}
          </div>
        </div>

        <div className="detail-layout">
          <div className="timeline-column">
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
                    insertResponseMacro(event.target.value)
                    event.currentTarget.value = ''
                  }}
                  aria-label="Macro"
                >
                  <option value="">Insert macro</option>
                  {composerMacroOptions.map(({ macro, score }) => (
                    <option value={macro.id} key={macro.id}>
                      {score ? `${macro.name} · ${score}%` : macro.shortcut ? `${macro.name} · ${macro.shortcut}` : macro.name}
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
                  className={attachmentDraft ? 'tool-toggle active' : 'tool-toggle'}
                  aria-pressed={Boolean(attachmentDraft)}
                  onClick={() => {
                    if (attachmentDraft) {
                      setAttachmentDraft(null)
                      const input = document.getElementById('composer-attachment-input') as HTMLInputElement | null
                      if (input) input.value = ''
                      return
                    }
                    document.getElementById('composer-attachment-input')?.click()
                  }}
                >
                  <Paperclip size={16} />
                  {attachmentDraft ? 'File ready' : 'Attach'}
                </button>
                <input
                  id="composer-attachment-input"
                  className="sr-only"
                  type="file"
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (!file) return
                    setAttachmentDraft({
                      filename: file.name || defaultAttachmentDraft(composerChannel).filename,
                      contentType: file.type || 'application/octet-stream',
                      sizeBytes: file.size,
                      file,
                    })
                  }}
                  aria-label="Choose attachment file"
                />
              </div>
              {attachmentDraft && (
                <div className="attachment-strip attachment-form">
                  <div className="attachment-form-status">
                    <Paperclip size={15} />
                    <span>
                      {attachmentDraft.file
                        ? 'File will upload to local storage, scan, and attach to the case timeline.'
                        : 'Metadata will be saved, scanned, and added to the case timeline.'}
                    </span>
                  </div>
                  <label>
                    File name
                    <input
                      value={attachmentDraft.filename}
                      readOnly={Boolean(attachmentDraft.file)}
                      onChange={(event) => updateAttachmentDraft({ filename: event.target.value, file: undefined })}
                      aria-label="Attachment file name"
                    />
                  </label>
                  <label>
                    Type
                    <input
                      value={attachmentDraft.contentType}
                      readOnly={Boolean(attachmentDraft.file)}
                      onChange={(event) => updateAttachmentDraft({ contentType: event.target.value, file: undefined })}
                      aria-label="Attachment content type"
                    />
                  </label>
                  <label>
                    Size KB
                    <input
                      type="number"
                      min="1"
                      value={Math.max(1, Math.round(attachmentDraft.sizeBytes / 1024))}
                      readOnly={Boolean(attachmentDraft.file)}
                      onChange={(event) =>
                        updateAttachmentDraft({
                          sizeBytes: Math.max(1, Number(event.target.value || 1)) * 1024,
                          file: undefined,
                        })
                      }
                      aria-label="Attachment size in KB"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setAttachmentDraft(null)
                      const input = document.getElementById('composer-attachment-input') as HTMLInputElement | null
                      if (input) input.value = ''
                    }}
                  >
                    Remove
                  </button>
                </div>
              )}
              {composerMode === 'handoff' && (
                <div className="handoff-composer-fields">
                  <label>
                    Receiving team
                    <select
                      value={effectiveHandoffTeam}
                      onChange={(event) => setHandoffTeam(event.target.value)}
                    >
                      {handoffTeamOptions.map((team) => (
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
                id="ticket-composer-input"
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
              {selectedConversation.copilot.responseMacros?.length ? (
                <div className="macro-suggestions" aria-label="Suggested macros">
                  {selectedConversation.copilot.responseMacros.slice(0, 2).map(({ macro, score, reasons }) => (
                    <button
                      type="button"
                      key={macro.id}
                      onClick={() => insertResponseMacro(macro.id)}
                    >
                      <strong>{macro.name}</strong>
                      <span>{score}% · {reasons.slice(0, 2).join(' · ')}</span>
                    </button>
                  ))}
                </div>
              ) : null}
              <div className="composer-footer">
                <span>{online ? 'Ready to send' : 'Offline: will send when connection returns'}</span>
                <button
                  className="primary-action"
                  type="button"
                  onClick={sendComposer}
                  disabled={!composerText.trim() && !attachmentDraft?.filename.trim()}
                >
                  <Send size={17} />
                  {online ? 'Send update' : 'Queue update'}
                </button>
              </div>
            </article>
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
                  {selectedConversation.copilot.knowledgeReasons?.length ? (
                    <small>{selectedConversation.copilot.knowledgeReasons.slice(0, 2).join(' · ')}</small>
                  ) : null}
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
              {[...selectedConversation.timeline].reverse().map((event) => {
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

          </div>

          <aside className="properties-panel">
            {duplicateSuggestions.length ? (
              <div className="property-card duplicate-guard-card">
                <span>
                  <GitBranch size={14} />
                  Potential duplicates
                </span>
                <div className="duplicate-suggestion-list">
                  {duplicateSuggestions.slice(0, 3).map((suggestion) => {
                    const suggestionConversation = state.conversations.find(
                      (conv) => conv.id === suggestion.ticketId,
                    )
                    const willGroup = !selectedConversation.caseId && !suggestionConversation?.caseId
                    const linkBusy = caseLinkBusy === suggestion.ticketId
                    return (
                      <div className="duplicate-suggestion" key={suggestion.ticketId}>
                        <div>
                          <strong>{suggestion.ticketNumber}</strong>
                          <small>{suggestion.score}% match · {titleCase(suggestion.status)}</small>
                        </div>
                        <p>{suggestion.subject}</p>
                        <div className="duplicate-reasons">
                          {suggestion.reasons.slice(0, 3).map((reason) => (
                            <span key={reason}>{reason}</span>
                          ))}
                        </div>
                        <div className="duplicate-suggestion-actions">
                          <button
                            type="button"
                            className="primary-action"
                            onClick={() => void linkSuggestionIntoCase(suggestion)}
                            disabled={linkBusy || caseLinkBusy !== ''}
                            aria-label={`Link ${suggestion.ticketNumber} with ${selectedConversation.ticketNumber} as one case`}
                          >
                            <Layers size={15} />
                            {linkBusy ? 'Linking' : willGroup ? 'Group as case' : 'Add to case'}
                          </button>
                          <button
                            type="button"
                            className="secondary-action"
                            onClick={() => mergeDuplicateTicket(suggestion)}
                            disabled={mergeTicketBusy === suggestion.ticketId}
                            aria-label={`Merge ${suggestion.ticketNumber} into ${selectedConversation.ticketNumber}`}
                          >
                            <ArrowRight size={15} />
                            {mergeTicketBusy === suggestion.ticketId ? 'Merging' : 'Merge'}
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : null}
            {(() => {
              const linkedCase = selectedConversation.caseId
                ? state.cases.find((item) => item.id === selectedConversation.caseId)
                : undefined
              if (linkedCase) {
                const siblings = linkedCase.ticketIds
                  .filter((id) => id !== selectedConversation.id)
                  .map((id) => state.conversations.find((conv) => conv.id === id))
                  .filter((conv): conv is OmniConversation => Boolean(conv))
                return (
                  <div className="property-card case-card">
                    <span>
                      <Layers size={14} />
                      Case · {linkedCase.publicId}
                    </span>
                    <strong>{linkedCase.title}</strong>
                    <small>
                      {linkedCase.ticketCount} ticket{linkedCase.ticketCount === 1 ? '' : 's'} across{' '}
                      {linkedCase.channels.length} channel{linkedCase.channels.length === 1 ? '' : 's'}
                    </small>
                    <div className="case-sibling-list">
                      {siblings.length ? (
                        siblings.map((conv) => (
                          <button
                            type="button"
                            key={conv.id}
                            onClick={() => selectConversation(conv.id)}
                            title={conv.subject}
                          >
                            <em>{state.channels.find((c) => c.id === conv.channelId)?.shortLabel ?? conv.channelId}</em>
                            {conv.ticketNumber} · {conv.subject}
                          </button>
                        ))
                      ) : (
                        <p className="case-empty">No other tickets linked yet.</p>
                      )}
                    </div>
                    <button
                      type="button"
                      className="secondary-action"
                      onClick={() => void detachCaseTicket(linkedCase.id, selectedConversation.id)}
                    >
                      Remove from case
                    </button>
                  </div>
                )
              }
              const customerOpenCases = state.cases.filter(
                (item) => item.customerId === selectedConversation.customerId,
              )
              return (
                <div className="property-card case-card">
                  <span>
                    <Layers size={14} />
                    Case
                  </span>
                  <small>Group this customer&rsquo;s communications across channels into one case.</small>
                  <button
                    type="button"
                    className="secondary-action"
                    onClick={() =>
                      void createCase({
                        customerId: selectedConversation.customerId,
                        title: selectedConversation.subject,
                        ticketIds: [selectedConversation.id],
                      })
                    }
                  >
                    <Plus size={14} />
                    Start a case from this ticket
                  </button>
                  {customerOpenCases.length ? (
                    <label className="case-attach-row">
                      <span>Add to existing case</span>
                      <select
                        value=""
                        onChange={(event) => {
                          if (event.target.value) {
                            void attachCaseTicket(event.target.value, selectedConversation.id)
                          }
                        }}
                      >
                        <option value="">Select a case…</option>
                        {customerOpenCases.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.publicId} · {item.title}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                </div>
              )
            })()}
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
            <label>
              Team
              <select
                value={selectedConversation.group}
                onChange={(event) => updateConversation(selectedConversation.id, { group: event.target.value })}
              >
                {state.supportGroups.some((group) => group.name === selectedConversation.group) ? null : (
                  <option value={selectedConversation.group}>{selectedConversation.group || 'Unassigned'}</option>
                )}
                {state.supportGroups.map((group) => (
                  <option value={group.name} key={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="property-card receiving-inbox-card">
              <span>
                <Inbox size={14} />
                Receiving inbox
              </span>
              <strong>{selectedConversation.group || 'Unassigned team'}</strong>
              <small className="receiving-inbox-addr">
                {receivingGroup?.teamEmail ? (
                  <>
                    <Mail size={12} />
                    {receivingGroup.teamEmail}
                  </>
                ) : (
                  'No team inbox set'
                )}
              </small>
              <small>Channel · {selectedChannel?.label ?? titleCase(selectedConversation.channelId)}</small>
            </div>
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
            {selectedTicketFields.length ? (
              <div className="property-card custom-field-card">
                <span>Ticket fields</span>
                <div className="ticket-field-stack">
                  {selectedTicketFields.map((field) => (
                    <label key={field.id}>
                      <span>
                        {field.label}
                        {field.required ? ' *' : ''}
                      </span>
                      {renderTicketFieldInput(
                        field,
                        selectedConversation.customFields[field.key],
                        (value) => updateConversationCustomField(field, value),
                      )}
                    </label>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="property-card">
              <span>Attachments</span>
              {attachmentEvents.length > 0 ? (
                <div className="compact-list">
                  {attachmentEvents.slice(-3).map((event) => (
                    <div key={event.id}>{event.body}</div>
                  ))}
                </div>
              ) : (
                <small>No customer files on this case yet.</small>
              )}
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
            <div className="property-card freshdesk-app-card">
              <span>Linked tickets</span>
              <strong>{selectedHandoffs.length + duplicateSuggestions.length}</strong>
              <small>Parent, child, duplicate, and team-service-task relationships.</small>
              <button
                className="secondary-action"
                type="button"
                onClick={() => setTicketDetailTab('linked')}
              >
                View links
              </button>
            </div>
            <div className="property-card freshdesk-app-card">
              <span>Time logs and AHT</span>
              <strong>{selectedAgent ? `${Math.max(6, selectedAgent.load * 2)}m` : 'No owner'}</strong>
              <small>Average handling time with task progress and owner load.</small>
              <button
                className="secondary-action"
                type="button"
                onClick={() => setTicketDetailTab('time')}
              >
                Open logs
              </button>
            </div>
            <div className="property-card freshdesk-app-card">
              <span>Wakanow CRM</span>
              <strong>{selectedCustomer.company}</strong>
              <small>{selectedCustomer.openValue} open value · {selectedCustomer.totalConversations} historical case(s).</small>
              <a
                className="secondary-action"
                href={routeHref({ screen: 'customers', customer: selectedCustomer.id })}
                onClick={(event) => handleAppLink(event, () => selectScreen('customers'))}
              >
                Open profile
              </a>
            </div>
          </aside>
        </div>
      </section>
    )
  }

  function renderInbox() {
    if (ticketDetailOpen) {
      return (
        <div className="desk-ticket-page">
          <div className="desk-detail-backbar">
            <button type="button" onClick={() => setTicketDetailOpen(false)}>
              <ArrowRight className="flip-x" size={15} />
              Back to tickets
            </button>
            <span className="desk-detail-backbar-title">
              {selectedConversation.subject}
              <b> #{selectedConversation.ticketNumber.replace(/\D/g, '') || selectedConversation.ticketNumber}</b>
            </span>
          </div>
          {renderConversationDetail()}
        </div>
      )
    }
    const now = Date.now()
    const DAY = 24 * 60 * 60 * 1000
    const PAGE_SIZE = 30
    const priorityRank: Record<Priority, number> = { urgent: 0, high: 1, medium: 2, low: 3 }

    const createdOk = (createdAt: string) => {
      if (inboxCreated === 'all') return true
      const ms = new Date(createdAt).getTime()
      if (!Number.isFinite(ms)) return false
      if (inboxCreated === 'today') return now - ms < DAY
      if (inboxCreated === 'week') return now - ms < 7 * DAY
      return now - ms < 30 * DAY
    }
    const dueOk = (conversation: OmniConversation) => {
      if (inboxDue === 'any') return true
      if (conversation.status === 'resolved') return false
      const due = new Date(conversation.resolutionDue).getTime()
      if (!Number.isFinite(due)) return false
      if (inboxDue === 'overdue') return due < now
      return due - now < DAY
    }
    const viewOk = (conversation: OmniConversation) => {
      if (inboxView === 'all-open') return conversation.status !== 'resolved'
      if (inboxView === 'my-open') {
        return conversation.assigneeId === selectedAgent?.id && conversation.status !== 'resolved'
      }
      if (inboxView === 'unassigned') {
        return (
          conversation.status !== 'resolved' &&
          (conversation.status === 'new' || conversation.assigneeId === '')
        )
      }
      if (inboxView === 'overdue') return conversation.slaState === 'breached'
      if (inboxView === 'resolved') return conversation.status === 'resolved'
      if (inboxView === 'whatsapp') return conversation.channelId === 'whatsapp'
      if (inboxView === 'ai-escalations') return conversation.sentiment === 'at-risk'
      return true
    }

    const baseRows = filteredConversations.filter(
      (conversation) =>
        viewOk(conversation) &&
        (inboxGroup === 'all' || conversation.group === inboxGroup) &&
        createdOk(conversation.createdAt) &&
        dueOk(conversation),
    )
    const sortedRows = [...baseRows].sort((a, b) => {
      if (inboxSort === 'priority') {
        return (
          priorityRank[a.priority] - priorityRank[b.priority] ||
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        )
      }
      if (inboxSort === 'updated') {
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      }
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    })

    const totalRows = sortedRows.length
    const maxPage = Math.max(0, Math.ceil(totalRows / PAGE_SIZE) - 1)
    const page = Math.min(inboxPage, maxPage)
    const startIndex = page * PAGE_SIZE
    const pageRows = sortedRows.slice(startIndex, startIndex + PAGE_SIZE)
    const pageIds = pageRows.map((conversation) => conversation.id)
    const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedTicketIds.includes(id))
    const groupNames = Array.from(new Set(state.conversations.map((conversation) => conversation.group)))
    const activeFilterCount =
      (state.filters.search ? 1 : 0) +
      (state.filters.assignee !== 'all' ? 1 : 0) +
      (state.filters.status !== 'all' ? 1 : 0) +
      (state.filters.priority !== 'all' ? 1 : 0) +
      (state.filters.channel !== 'all' ? 1 : 0) +
      (state.filters.sentiment !== 'all' ? 1 : 0) +
      (state.filters.sla !== 'all' ? 1 : 0) +
      (inboxGroup !== 'all' ? 1 : 0) +
      (inboxCreated !== 'all' ? 1 : 0) +
      (inboxDue !== 'any' ? 1 : 0)

    return (
      <div className="desk-ticket-page">
        <section className="desk-ticket-toolbar" aria-label="Ticket list controls">
          <label className="desk-check-label" aria-label="Select all tickets on this page">
            <input type="checkbox" checked={allPageSelected} onChange={() => toggleSelectAllTickets(pageIds)} />
          </label>
          <label>
            <span>Sort by:</span>
            <select value={inboxSort} onChange={(event) => setInboxSort(event.target.value as typeof inboxSort)}>
              <option value="created">Date created</option>
              <option value="updated">Last updated</option>
              <option value="priority">Priority</option>
            </select>
          </label>
          <span className="desk-toolbar-spacer" />
          <label>
            <span>Layout:</span>
            <select value={inboxLayout} onChange={(event) => setInboxLayout(event.target.value as typeof inboxLayout)}>
              <option value="card">Card</option>
              <option value="table">Table</option>
            </select>
          </label>
          <button type="button" onClick={() => exportTicketsCsv(sortedRows)} disabled={totalRows === 0}>
            <Download size={14} />
            Export
          </button>
          <span className="desk-ticket-range">
            {totalRows
              ? `${startIndex + 1} - ${Math.min(startIndex + PAGE_SIZE, totalRows)} of ${totalRows}`
              : '0 tickets'}
          </span>
          <button
            type="button"
            aria-label="Previous page"
            disabled={page <= 0}
            onClick={() => setInboxPage(Math.max(0, page - 1))}
          >
            <ArrowRight className="flip-x" size={14} />
          </button>
          <button
            type="button"
            aria-label="Next page"
            disabled={page >= maxPage}
            onClick={() => setInboxPage(Math.min(maxPage, page + 1))}
          >
            <ArrowRight size={14} />
          </button>
          <button
            type="button"
            className="desk-filter-toggle"
            aria-expanded={inboxFiltersOpen}
            onClick={() => setInboxFiltersOpen((open) => !open)}
          >
            <Filter size={14} />
            Filters{activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}
          </button>
        </section>

        {selectedTicketIds.length > 0 && (
          <section className="desk-bulk-bar" aria-label="Bulk ticket actions">
            <strong>{selectedTicketIds.length} selected</strong>
            <label>
              <span>Assign to</span>
              <select
                value=""
                onChange={(event) => {
                  if (event.target.value) applyBulkTicketUpdate({ assigneeId: event.target.value })
                }}
              >
                <option value="">Choose agent…</option>
                {state.agents.map((agent) => (
                  <option value={agent.id} key={agent.id}>{agent.name}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Set status</span>
              <select
                value=""
                onChange={(event) => {
                  if (event.target.value) applyBulkTicketUpdate({ status: event.target.value as ConversationStatus })
                }}
              >
                <option value="">Choose status…</option>
                {statusOptions.filter((option): option is ConversationStatus => option !== 'all').map((status) => (
                  <option value={status} key={status}>{titleCase(status)}</option>
                ))}
              </select>
            </label>
            <button type="button" onClick={() => setSelectedTicketIds([])}>
              Clear selection
            </button>
          </section>
        )}

        <div className={`desk-ticket-layout ${inboxFiltersOpen ? '' : 'filters-collapsed'}`}>
          <section
            className={`desk-ticket-list ${inboxLayout === 'table' ? 'table-layout' : ''}`}
            aria-label="All tickets"
          >
            {totalRows > 0 && (
              <button className="desk-update-chip" type="button" onClick={() => refreshBackend()}>
                <RefreshCw size={15} />
                Refresh
              </button>
            )}
            {pageRows.length > 0 ? (
              pageRows.map((conversation) => {
                const customer = state.customers.find((item) => item.id === conversation.customerId)
                const channel = state.channels.find((item) => item.id === conversation.channelId)
                const selected = selectedConversation.id === conversation.id
                const checked = selectedTicketIds.includes(conversation.id)
                const resolved = conversation.status === 'resolved'
                const promiseText = resolved ? 'Resolved on time' : promiseLabel(conversation)
                return (
                  <article
                    className={`desk-ticket-row ${selected ? 'active' : ''} ${checked ? 'checked' : ''} status-${conversation.status}`}
                    key={conversation.id}
                  >
                    <label className="desk-check-label" aria-label={`Select ${conversation.ticketNumber}`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleTicketSelection(conversation.id)}
                      />
                    </label>
                    <button
                      type="button"
                      className="desk-ticket-avatar"
                      onClick={() => openConversationInInbox(conversation)}
                      aria-label={`Open ${conversation.ticketNumber}`}
                    >
                      {initials(customer?.name ?? conversation.subject)}
                    </button>
                    <div className="desk-ticket-main">
                      <div className="desk-ticket-subject">
                        {conversation.status === 'new' && <span className="desk-new-badge">New</span>}
                        {conversation.tags.slice(0, 1).map((tag) => (
                          <span className="desk-soft-badge" key={tag}>{tag}</span>
                        ))}
                        <button type="button" onClick={() => openConversationInInbox(conversation)}>
                          {conversation.subject} <b>#{conversation.ticketNumber.replace(/\D/g, '') || conversation.ticketNumber}</b>
                        </button>
                      </div>
                      <div className="desk-ticket-meta">
                        <span>{channel?.shortLabel ?? titleCase(conversation.channelId)}</span>
                        <span>{customer?.name ?? 'Unknown contact'}</span>
                        <span>{resolved ? 'Closed' : 'Created'} {relativeWorkTime(conversation.createdAt)}</span>
                        <span className={`desk-due-label sla-${conversation.slaState}`}>{promiseText}</span>
                      </div>
                    </div>
                    <div className="desk-ticket-side">
                      <div className={`desk-inline-select priority-${conversation.priority}`}>
                        <span className="desk-inline-dot" />
                        <select
                          value={conversation.priority}
                          onChange={(event) =>
                            updateConversation(conversation.id, { priority: event.target.value as Priority })
                          }
                          aria-label={`Priority for ${conversation.ticketNumber}`}
                        >
                          {priorityOptions.filter((option): option is Priority => option !== 'all').map((priority) => (
                            <option value={priority} key={priority}>{titleCase(priority)}</option>
                          ))}
                        </select>
                      </div>
                      <div className="desk-inline-select desk-owner-select">
                        <Users size={13} />
                        <select
                          value={conversation.assigneeId}
                          onChange={(event) =>
                            updateConversation(conversation.id, { assigneeId: event.target.value })
                          }
                          aria-label={`Owner for ${conversation.ticketNumber}`}
                        >
                          <option value="">Unassigned</option>
                          {state.agents.map((agent) => (
                            <option value={agent.id} key={agent.id}>{agent.name}</option>
                          ))}
                        </select>
                      </div>
                      <div className={`desk-inline-select status-${conversation.status}`}>
                        <select
                          value={conversation.status}
                          onChange={(event) =>
                            updateConversation(conversation.id, { status: event.target.value as ConversationStatus })
                          }
                          aria-label={`Status for ${conversation.ticketNumber}`}
                        >
                          {statusOptions.filter((option): option is ConversationStatus => option !== 'all').map((status) => (
                            <option value={status} key={status}>{titleCase(status)}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </article>
                )
              })
            ) : (
              <div className="empty-state compact">
                <strong>No tickets match these filters</strong>
                <span>Clear filters or search another customer, topic, or label.</span>
                <button className="secondary-action" type="button" onClick={resetAllInboxFilters}>
                  Clear filters
                </button>
              </div>
            )}
          </section>

          {inboxFiltersOpen && (
            <aside className="desk-filter-sidebar" aria-label="Ticket filters">
              <div className="desk-filter-head">
                <strong>Filters</strong>
                <button type="button" onClick={resetAllInboxFilters}>Reset</button>
              </div>
              <label className="desk-filter-search">
                <Search size={16} />
                <input
                  value={state.filters.search}
                  onChange={(event) => setFilters({ search: event.target.value })}
                  placeholder="Search subject, ticket #, email or phone"
                  aria-label="Search tickets by subject, ticket number, customer email or phone"
                />
              </label>
              <label>
                <span>Agents</span>
                <select value={state.filters.assignee} onChange={(event) => setFilters({ assignee: event.target.value })}>
                  <option value="all">Any agent</option>
                  {state.agents.map((agent) => (
                    <option value={agent.id} key={agent.id}>{agent.name}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Groups</span>
                <select value={inboxGroup} onChange={(event) => setInboxGroup(event.target.value)}>
                  <option value="all">Any group</option>
                  {groupNames.map((group) => (
                    <option value={group} key={group}>{group}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Created</span>
                <select value={inboxCreated} onChange={(event) => setInboxCreated(event.target.value as typeof inboxCreated)}>
                  <option value="all">Any time</option>
                  <option value="today">Today</option>
                  <option value="week">This week</option>
                  <option value="last-30">Last 30 days</option>
                </select>
              </label>
              <label>
                <span>Resolution due</span>
                <select value={inboxDue} onChange={(event) => setInboxDue(event.target.value as typeof inboxDue)}>
                  <option value="any">Any time</option>
                  <option value="today">Due today</option>
                  <option value="overdue">Overdue</option>
                </select>
              </label>
              <label>
                <span>Status Include</span>
                <select value={state.filters.status} onChange={(event) => setFilters({ status: event.target.value as ConversationStatus | 'all' })}>
                  <option value="all">Any status</option>
                  {statusOptions.filter((option): option is ConversationStatus => option !== 'all').map((status) => (
                    <option value={status} key={status}>{titleCase(status)}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Priorities Include</span>
                <select value={state.filters.priority} onChange={(event) => setFilters({ priority: event.target.value as Priority | 'all' })}>
                  <option value="all">Any</option>
                  {priorityOptions.filter((option): option is Priority => option !== 'all').map((priority) => (
                    <option value={priority} key={priority}>{titleCase(priority)}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Sources Include</span>
                <select value={state.filters.channel} onChange={(event) => setFilters({ channel: event.target.value as ChannelId | 'all' })}>
                  <option value="all">Any</option>
                  {state.channels.map((channel) => (
                    <option value={channel.id} key={channel.id}>{channel.label}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Tags</span>
                <select value={state.filters.sentiment} onChange={(event) => setFilters({ sentiment: event.target.value as Sentiment | 'all' })}>
                  <option value="all">Any</option>
                  {sentimentOptions.filter((option): option is Sentiment => option !== 'all').map((sentiment) => (
                    <option value={sentiment} key={sentiment}>{sentimentLabels[sentiment]}</option>
                  ))}
                </select>
              </label>
            </aside>
          )}
        </div>
      </div>
    )
  }

  function renderQuickCreatePanel() {
    if (!quickCreateOpen) return null
    const quickTicketFields = ticketFieldsForChannel(quickTicket.channelId)

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
            {quickTicketFields.length ? (
              <div className="quick-custom-fields span-all" aria-label="Ticket fields">
                {quickTicketFields.map((field) => (
                  <label key={field.id}>
                    <span>
                      {field.label}
                      {field.required ? ' *' : ''}
                    </span>
                    {renderTicketFieldInput(
                      field,
                      quickTicket.customFields?.[field.key],
                      (value) => updateQuickCustomField(field, value),
                    )}
                    {field.helpText ? <small>{field.helpText}</small> : null}
                  </label>
                ))}
              </div>
            ) : null}
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

  function handleGlobalSearchResult(result: BackendGlobalSearchResult) {
    setGlobalSearchOpen(false)
    const ticketId = typeof result.metadata.ticket_id === 'string' ? result.metadata.ticket_id : result.entity_id
    if (result.type === 'ticket') {
      selectScreen('inbox')
      selectConversation(result.entity_id)
      return
    }
    if (result.type === 'customer') {
      selectScreen('customers')
      selectCustomer(result.entity_id)
      return
    }
    if (result.type === 'support_group') {
      selectScreen('admin')
      setSetupSection('people')
      setPeopleView('groups')
      return
    }
    if (result.type === 'handoff') {
      selectScreen('handoffs')
      if (ticketId) selectConversation(ticketId)
      return
    }
    if (result.type === 'knowledge') {
      selectScreen('knowledge')
      return
    }
    if (result.type === 'agent') {
      selectScreen('workforce')
      return
    }
    selectScreen('customers')
  }

  function globalSearchHref(result: BackendGlobalSearchResult) {
    if (result.type === 'ticket') return routeHref({ screen: 'inbox', conversation: result.entity_id })
    if (result.type === 'customer') return routeHref({ screen: 'customers', customer: result.entity_id })
    if (result.type === 'support_group') return routeHref({ screen: 'admin' })
    if (result.type === 'handoff') return routeHref({ screen: 'handoffs' })
    if (result.type === 'knowledge') return routeHref({ screen: 'knowledge' })
    if (result.type === 'agent') return routeHref({ screen: 'workforce' })
    return routeHref({ screen: 'command' })
  }

  function renderGlobalSearchResults() {
    const query = state.filters.search.trim()
    if (!globalSearchOpen || query.length < 2) return null

    return (
      <section className="global-search-popover" aria-label="Global search results">
        <div className="global-search-status">
          <span>
            {globalSearchLoading
              ? 'Searching...'
              : `${globalSearchResults.length} result${globalSearchResults.length === 1 ? '' : 's'}`}
          </span>
          <button
            type="button"
            className="icon-button"
            aria-label="Close search"
            onClick={() => setGlobalSearchOpen(false)}
          >
            <X size={14} />
          </button>
        </div>
        {globalSearchError ? <div className="global-search-empty">{globalSearchError}</div> : null}
        {!globalSearchError && !globalSearchLoading && !globalSearchResults.length ? (
          <div className="global-search-empty">No matching records.</div>
        ) : null}
        {!globalSearchError && globalSearchResults.length ? (
          <div className="global-search-list">
            {globalSearchResults.map((result) => (
              <a
                key={result.id}
                href={globalSearchHref(result)}
                onClick={(event) => handleAppLink(event, () => handleGlobalSearchResult(result))}
              >
                <span className="search-result-type">{titleCase(result.type.replace('_', ' '))}</span>
                <strong>{result.title}</strong>
                <small>{result.subtitle}</small>
              </a>
            ))}
          </div>
        ) : null}
      </section>
    )
  }

  function renderFreshchatModulePanel() {
    if (channelConsoleView === 'inbox') return null
    const activeModule = freshchatConsoleViews.find((view) => view.id === channelConsoleView)
    const ActiveIcon = activeModule?.icon ?? MessageCircle
    const connectorAccounts = backendSnapshot?.connectorAccounts ?? []
    const chatChannels = state.channels.filter((channel) =>
      ['chat', 'whatsapp', 'instagram', 'facebook', 'sms'].includes(channel.id),
    )

    function moduleBody() {
      if (channelConsoleView === 'dashboard') {
        const totalQueue = chatChannels.reduce((sum, channel) => sum + channel.queueDepth, 0)
        const activeSessions = chatChannels.reduce((sum, channel) => sum + channel.activeSessions, 0)
        const avgWait = chatChannels.length
          ? Math.round(
              chatChannels.reduce((sum, channel) => sum + channel.avgWaitMinutes, 0) / chatChannels.length,
            )
          : 0
        const atRisk = chatChannels.reduce((sum, channel) => sum + channel.slaRisk, 0)
        return (
          <>
            <div className="freshchat-kpi-row">
              <article>
                <strong>{totalQueue}</strong>
                <span>Queued conversations</span>
              </article>
              <article>
                <strong>{activeSessions}</strong>
                <span>Active sessions</span>
              </article>
              <article>
                <strong>{avgWait}m</strong>
                <span>Avg wait</span>
              </article>
              <article>
                <strong>{atRisk}</strong>
                <span>SLA risk</span>
              </article>
            </div>
            <div className="freshchat-module-list">
              {chatChannels.map((channel) => (
                <div key={channel.id} className="freshchat-module-row">
                  <strong>{channel.label}</strong>
                  <span>{channel.queueDepth} queued · {channel.activeSessions} active</span>
                  <em className={`chip status-${channel.status === 'healthy' ? 'done' : channel.status === 'degraded' ? 'progress' : 'pending'}`}>
                    {titleCase(channel.status)}
                  </em>
                </div>
              ))}
            </div>
          </>
        )
      }
      if (channelConsoleView === 'campaigns') {
        const campaigns = state.scenarioAutomations
        if (campaigns.length === 0) {
          return (
            <p className="setup-module-hint">
              No proactive campaigns yet. Build one in Automation → Proactive outreach.
            </p>
          )
        }
        return (
          <div className="freshchat-module-list">
            {campaigns.map((campaign) => (
              <div key={campaign.id} className="freshchat-module-row">
                <strong>{campaign.name}</strong>
                <span>{campaign.actions.length} action{campaign.actions.length === 1 ? '' : 's'}</span>
                <em className={`chip status-${campaign.active ? 'done' : 'pending'}`}>
                  {campaign.active ? 'Live' : 'Draft'}
                </em>
              </div>
            ))}
          </div>
        )
      }
      if (channelConsoleView === 'people') {
        const recent = state.customers.slice(0, 6)
        return (
          <>
            <div className="freshchat-module-list">
              {recent.map((customer) => (
                <div key={customer.id} className="freshchat-module-row">
                  <strong>{customer.name}</strong>
                  <span>{customer.company} · {customer.email}</span>
                  <em className="chip status-progress">{customer.totalConversations} convos</em>
                </div>
              ))}
            </div>
            <button type="button" className="secondary-action" onClick={() => selectScreen('customers')}>
              <Users size={14} />
              Open Contacts ({state.customers.length})
            </button>
          </>
        )
      }
      if (channelConsoleView === 'reports') {
        return (
          <>
            <div className="freshchat-module-list">
              {state.savedReports.length === 0 ? (
                <p className="setup-module-hint">No saved reports yet. Create one in Analytics.</p>
              ) : (
                state.savedReports.slice(0, 6).map((report) => (
                  <div key={report.id} className="freshchat-module-row">
                    <strong>{report.name}</strong>
                    <span>{titleCase(report.reportType)} · {report.cadence === 'none' ? 'On demand' : titleCase(report.cadence)}</span>
                    <em className={`chip status-${report.active ? 'done' : 'pending'}`}>
                      {report.active ? 'Active' : 'Paused'}
                    </em>
                  </div>
                ))
              )}
            </div>
            <button type="button" className="secondary-action" onClick={() => selectScreen('analytics')}>
              <BarChart3 size={14} />
              Open Analytics
            </button>
          </>
        )
      }
      if (channelConsoleView === 'marketplace') {
        if (connectorAccounts.length === 0) {
          return (
            <p className="setup-module-hint">
              No connected integrations yet. Add channel credentials in Setup → Channels.
            </p>
          )
        }
        return (
          <div className="freshchat-module-list">
            {connectorAccounts.map((account) => (
              <div key={account.id} className="freshchat-module-row">
                <strong>{account.display_name}</strong>
                <span>{titleCase(account.provider)} · {account.account_identifier || 'No identifier'}</span>
                <em className={`chip status-${account.status === 'connected' ? 'done' : account.status === 'error' || account.status === 'action_required' ? 'pending' : 'progress'}`}>
                  {titleCase(account.status.replace(/_/g, ' '))}
                </em>
              </div>
            ))}
          </div>
        )
      }
      if (channelConsoleView === 'settings') {
        return (
          <>
            <p className="setup-module-hint">
              Account, channel, agent, and credential settings are managed in Setup.
            </p>
            <button type="button" className="secondary-action" onClick={() => selectScreen('admin')}>
              <Settings size={14} />
              Open Setup
            </button>
          </>
        )
      }
      // ai-studio
      return (
        <>
          <div className="freshchat-module-list">
            {state.rules.length === 0 ? (
              <p className="setup-module-hint">No automation rules yet. Build one in Automation.</p>
            ) : (
              state.rules.slice(0, 6).map((rule) => (
                <div key={rule.id} className="freshchat-module-row">
                  <strong>{rule.name}</strong>
                  <span>{rule.trigger}</span>
                  <em className={`chip status-${rule.status}`}>{rule.health}%</em>
                </div>
              ))
            )}
          </div>
          <button type="button" className="secondary-action" onClick={() => selectScreen('automation')}>
            <Workflow size={14} />
            Open Automation
          </button>
        </>
      )
    }

    return (
      <section className="panel freshchat-module-panel">
        <div className="panel-head">
          <div>
            <span>Omnichat module</span>
            <h2>{activeModule?.label ?? 'Module'}</h2>
          </div>
          <ActiveIcon size={20} />
        </div>
        {moduleBody()}
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
    const channelChatBaseConversations = state.conversations.filter(
      (conversation) => conversation.channelId === activeDirectChannelId,
    )
    const channelConversations = channelChatBaseConversations
      .filter((conversation) =>
        directChatFilter === 'all'
          ? true
          : directChatFilter === 'resolved'
            ? conversation.status === 'resolved'
            : conversation.status !== 'resolved',
      )
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
            <div className="freshchat-view-stack" aria-label="Omnichat views">
              <div className="view-rail-head">
                <strong>{activeChannel.label} views</strong>
              </div>
              <div className="view-group">
                {(
                  [
                    ['all', 'All conversations'],
                    ['open', 'Open & unresolved'],
                    ['resolved', 'Resolved'],
                  ] as const
                ).map(([value, label]) => {
                  const count =
                    value === 'all'
                      ? channelChatBaseConversations.length
                      : value === 'resolved'
                        ? channelChatBaseConversations.filter((c) => c.status === 'resolved').length
                        : channelChatBaseConversations.filter((c) => c.status !== 'resolved').length
                  return (
                    <button
                      type="button"
                      key={value}
                      className={directChatFilter === value ? 'active' : ''}
                      aria-pressed={directChatFilter === value}
                      onClick={() => setDirectChatFilter(value)}
                    >
                      <small>{label}</small>
                      <strong>{count}</strong>
                    </button>
                  )
                })}
              </div>
            </div>
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
                <div className="direct-chat-messages">
                  {[...channelEvents].reverse().map((event) => (
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
        <section className="freshchat-console-shell" aria-label="Omnichat console modules">
          <div className="freshchat-console-tabs" role="tablist" aria-label="Omnichat modules">
            {freshchatConsoleViews.map(({ id, label, icon: ModuleIcon }) => (
              <button
                type="button"
                key={id}
                role="tab"
                aria-selected={channelConsoleView === id}
                className={channelConsoleView === id ? 'active' : ''}
                onClick={() => setChannelConsoleView(id)}
              >
                <ModuleIcon size={16} />
                {label}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="freshchat-global-search"
            onClick={() => setGlobalSearchOpen(true)}
            aria-label="Search conversations and people"
          >
            <Search size={15} />
            <span>Search conversations and people</span>
          </button>
        </section>
        {renderFreshchatModulePanel()}
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
    const query = state.filters.search.trim().toLowerCase()
    const queryDigits = query.replace(/\D/g, '')
    const customers = query
      ? state.customers.filter(
          (customer) =>
            customer.name.toLowerCase().includes(query) ||
            customer.email.toLowerCase().includes(query) ||
            customer.phone.toLowerCase().includes(query) ||
            (queryDigits.length >= 6 &&
              [customer.phone, ...customer.contactMethods.map((method) => method.value)]
                .join(' ')
                .replace(/\D/g, '')
                .includes(queryDigits)) ||
            customer.company.toLowerCase().includes(query) ||
            customer.tags.some((tag) => tag.toLowerCase().includes(query)),
        )
      : state.customers
    const companies = backendSnapshot?.companies ?? []

    return (
      <div className="management-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Customer 360</span>
              <h2>Profiles, value, and open work</h2>
            </div>
            <button
              type="button"
              className="primary-action"
              aria-expanded={customerFormOpen}
              onClick={() => setCustomerFormOpen((open) => !open)}
            >
              <Plus size={16} />
              New customer
            </button>
          </div>
          <label className="customer-search">
            <Search size={15} />
            <input
              value={state.filters.search}
              onChange={(event) => setFilters({ search: event.target.value })}
              placeholder="Search customers by name, email, phone, company, or tag"
              aria-label="Search customers"
            />
          </label>
          {customerFormOpen ? (
            <form className="user-create-form canned-response-form" onSubmit={handleCreateCustomer}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={customerDraft.name}
                    onChange={(event) =>
                      setCustomerDraft((current) => ({ ...current, name: event.target.value }))
                    }
                    placeholder="Ada Obi"
                    disabled={customerBusy}
                  />
                </label>
                <label>
                  <span>Email</span>
                  <input
                    required
                    type="email"
                    value={customerDraft.email}
                    onChange={(event) =>
                      setCustomerDraft((current) => ({ ...current, email: event.target.value }))
                    }
                    placeholder="ada@example.com"
                    disabled={customerBusy}
                  />
                </label>
                <label>
                  <span>Company</span>
                  <select
                    value={customerDraft.companyId}
                    onChange={(event) =>
                      setCustomerDraft((current) => ({ ...current, companyId: event.target.value }))
                    }
                    disabled={customerBusy}
                  >
                    <option value="">Independent customer</option>
                    {companies.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="canned-form-row">
                <label>
                  <span>Location</span>
                  <input
                    value={customerDraft.location}
                    onChange={(event) =>
                      setCustomerDraft((current) => ({ ...current, location: event.target.value }))
                    }
                    placeholder="Lagos, Nigeria"
                    disabled={customerBusy}
                  />
                </label>
                <label>
                  <span>Tags (comma separated)</span>
                  <input
                    value={customerDraft.tags}
                    onChange={(event) =>
                      setCustomerDraft((current) => ({ ...current, tags: event.target.value }))
                    }
                    placeholder="vip, corporate"
                    disabled={customerBusy}
                  />
                </label>
              </div>
              <label className="canned-form-full">
                <span>Notes</span>
                <textarea
                  rows={2}
                  value={customerDraft.notes}
                  onChange={(event) =>
                    setCustomerDraft((current) => ({ ...current, notes: event.target.value }))
                  }
                  placeholder="Account context, preferences, or escalation history."
                  disabled={customerBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={
                  customerBusy ||
                  customerDraft.name.trim().length < 1 ||
                  customerDraft.email.trim().length < 3
                }
              >
                <Plus size={16} />
                Create customer
              </button>
            </form>
          ) : null}
          {customers.length === 0 ? (
            <p className="setup-module-hint">
              {query ? 'No customers match your search.' : 'No customers yet. Add one to get started.'}
            </p>
          ) : (
            <div className="customer-grid">
              {customers.map((customer) => (
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
          )}
        </section>
        {renderCustomer360()}
      </div>
    )
  }

  function renderKnowledge() {
    const query = state.filters.search.trim().toLowerCase()
    const articles = state.articles
      .filter((article) => {
        if (!query) return true
        return (
          article.title.toLowerCase().includes(query) ||
          article.category.toLowerCase().includes(query) ||
          article.language.toLowerCase().includes(query) ||
          article.intents.some((intent) => intent.toLowerCase().includes(query))
        )
      })
      .slice()
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    const categories = Array.from(new Set(articles.map((article) => article.category))).sort()
    const statusTone: Record<KnowledgeArticle['status'], string> = {
      published: 'status-done',
      review: 'status-progress',
      draft: 'status-pending',
    }
    const statusOptions: KnowledgeArticle['status'][] = ['draft', 'review', 'published']
    const publishedCount = state.articles.filter((article) => article.status === 'published').length
    const reviewCount = state.articles.filter((article) => article.status === 'review').length
    const draftCount = state.articles.filter((article) => article.status === 'draft').length

    return (
      <div className="desk-solutions-page">
        <section className="desk-solutions-toolbar" aria-label="Knowledge base controls">
          <label className="desk-solution-search">
            <Search size={16} />
            <input
              value={state.filters.search}
              onChange={(event) => setFilters({ search: event.target.value })}
              placeholder="Search articles"
              aria-label="Search articles"
            />
          </label>
          <span className="desk-toolbar-spacer" />
          <span className="kb-stat-pills" aria-label="Article counts">
            <em className="chip status-done">{publishedCount} published</em>
            <em className="chip status-progress">{reviewCount} in review</em>
            <em className="chip status-pending">{draftCount} draft</em>
          </span>
          <button
            type="button"
            className="desk-blue-action"
            aria-expanded={articleFormOpen}
            onClick={() => setArticleFormOpen((open) => !open)}
          >
            <Plus size={14} />
            New article
          </button>
        </section>

        {articleFormOpen ? (
          <form className="user-create-form canned-response-form kb-article-form" onSubmit={handleCreateKnowledgeArticle}>
            <div className="canned-form-row">
              <label>
                <span>Title</span>
                <input
                  required
                  value={articleDraft.title}
                  onChange={(event) =>
                    setArticleDraft((current) => ({ ...current, title: event.target.value }))
                  }
                  placeholder="How to reschedule a flight booking"
                  disabled={articleBusy}
                />
              </label>
              <label>
                <span>Category</span>
                <input
                  value={articleDraft.category}
                  onChange={(event) =>
                    setArticleDraft((current) => ({ ...current, category: event.target.value }))
                  }
                  placeholder="Operations"
                  disabled={articleBusy}
                />
              </label>
              <label>
                <span>Status</span>
                <select
                  value={articleDraft.status}
                  onChange={(event) =>
                    setArticleDraft((current) => ({
                      ...current,
                      status: event.target.value as KnowledgeArticle['status'],
                    }))
                  }
                  disabled={articleBusy}
                >
                  {statusOptions.map((status) => (
                    <option key={status} value={status}>
                      {titleCase(status)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Language</span>
                <select
                  value={articleDraft.language}
                  onChange={(event) =>
                    setArticleDraft((current) => ({ ...current, language: event.target.value }))
                  }
                  disabled={articleBusy}
                >
                  {['en', 'fr', 'pt', 'ar'].map((language) => (
                    <option key={language} value={language}>
                      {language.toUpperCase()}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="canned-form-full">
              <span>Body</span>
              <textarea
                required
                rows={4}
                value={articleDraft.body}
                onChange={(event) =>
                  setArticleDraft((current) => ({ ...current, body: event.target.value }))
                }
                placeholder="Write the answer agents and customers will see in the portal."
                disabled={articleBusy}
              />
            </label>
            <div className="kb-article-form-actions">
              <button type="button" onClick={() => setArticleFormOpen(false)} disabled={articleBusy}>
                Cancel
              </button>
              <button
                type="submit"
                className="primary-action"
                disabled={
                  articleBusy ||
                  articleDraft.title.trim().length < 1 ||
                  articleDraft.body.trim().length < 1
                }
              >
                <Plus size={16} />
                Create article
              </button>
            </div>
          </form>
        ) : null}

        {articles.length === 0 ? (
          <p className="setup-module-hint">
            {query
              ? 'No articles match your search.'
              : 'No knowledge articles yet. Create one to start building your help center.'}
          </p>
        ) : (
          <section className="kb-category-stack" aria-label="Knowledge base articles">
            {categories.map((category) => {
              const grouped = articles.filter((article) => article.category === category)
              return (
                <article className="kb-category-block" key={category}>
                  <header>
                    <BookOpen size={17} />
                    <h2>{category}</h2>
                    <strong>{grouped.length}</strong>
                  </header>
                  <div className="kb-article-list">
                    {grouped.map((article) => {
                      const extraTags = article.intents.filter((intent) => intent !== article.category)
                      return (
                      <div className="kb-article-row" key={article.id}>
                        <div className="kb-article-main">
                          <strong>{article.title}</strong>
                          <span>
                            {article.language.toUpperCase()} · Updated {formatTime(article.updatedAt)}
                            {extraTags.length > 0 ? ` · ${extraTags.join(', ')}` : ''}
                          </span>
                        </div>
                        <em className={`chip ${statusTone[article.status]}`}>{titleCase(article.status)}</em>
                        <label className="kb-article-status">
                          <span>Status</span>
                          <select
                            value={article.status}
                            onChange={(event) =>
                              void setArticleStatus(article, event.target.value as KnowledgeArticle['status'])
                            }
                            disabled={articleBusy}
                          >
                            {statusOptions.map((status) => (
                              <option key={status} value={status}>
                                {titleCase(status)}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      )
                    })}
                  </div>
                </article>
              )
            })}
          </section>
        )}
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
                    const linkedConversation = handoff.linkedConversationId
                      ? state.conversations.find((item) => item.id === handoff.linkedConversationId)
                      : undefined
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
                          {linkedConversation && linkedConversation.id !== conversation?.id && (
                            <a
                              className="secondary-action"
                              href={routeHref({
                                screen: 'inbox',
                                conversation: linkedConversation.id,
                                customer: linkedConversation.customerId,
                              })}
                              onClick={(event) =>
                                handleAppLink(event, () => openConversationInInbox(linkedConversation))
                              }
                              aria-label={`Open ${linkedConversation.ticketNumber} team ticket`}
                            >
                              Team ticket
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
    const analyticsRollups =
      backendSnapshot?.analyticsRollups ?? backendSnapshot?.analytics_rollups ?? []
    const latestRollup = analyticsRollups[0]
    const rollupChannelVolume = latestRollup?.channel_volume ?? {}
    const maxRollupVolume = Math.max(...Object.values(rollupChannelVolume), 1)
    const csatFeedback = backendSnapshot?.csatFeedback ?? backendSnapshot?.csat_feedback ?? []
    const backendCsat = backendSnapshot?.analytics.avg_csat ?? latestRollup?.avg_csat
    const displayCsat = backendCsat == null ? metrics.csat : backendCsat.toFixed(1)
    return (
      <div className="management-grid">
        <section className="panel span-2 analytics-library-panel">
          <div className="panel-head">
            <div>
              <span>Report library</span>
              <h2>Analytics catalog, saved reports, and scheduled exports</h2>
            </div>
            <BarChart3 size={20} />
          </div>
          <div className="report-library-tabs" role="tablist" aria-label="Analytics report groups">
            {[
              { id: 'catalog' as AnalyticsReportGroup, label: 'Catalog' },
              { id: 'saved' as AnalyticsReportGroup, label: 'Saved reports' },
              { id: 'scheduled' as AnalyticsReportGroup, label: 'Scheduled exports' },
            ].map((tab) => (
              <button
                type="button"
                key={tab.id}
                role="tab"
                aria-selected={analyticsReportGroup === tab.id}
                className={analyticsReportGroup === tab.id ? 'active' : ''}
                onClick={() => setAnalyticsReportGroup(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          {analyticsReportGroup === 'catalog' ? (
            <div className="report-card-grid">
              {analyticsReportCatalog.catalog.map((report) => (
                <article key={report.title}>
                  <div>
                    <strong>{report.title}</strong>
                    <span>{report.detail}</span>
                  </div>
                  <em className="chip status-done">{report.badge}</em>
                  <div className="report-card-actions">
                    <button type="button" onClick={exportAnalyticsRollupsCsv}>
                      <Download size={13} />
                      Export CSV
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <>
              <form className="user-create-form canned-response-form report-create-form" onSubmit={handleCreateSavedReport}>
                <div className="canned-form-row">
                  <label>
                    <span>Report name</span>
                    <input
                      required
                      value={reportDraft.name}
                      onChange={(event) => setReportDraft((current) => ({ ...current, name: event.target.value }))}
                      placeholder="Executive service review"
                      disabled={reportBusy}
                    />
                  </label>
                  <label>
                    <span>Type</span>
                    <select
                      value={reportDraft.reportType}
                      onChange={(event) => setReportDraft((current) => ({ ...current, reportType: event.target.value }))}
                      disabled={reportBusy}
                    >
                      {['tickets', 'chat', 'csat', 'team', 'ai'].map((type) => (
                        <option key={type} value={type}>{titleCase(type)}</option>
                      ))}
                    </select>
                  </label>
                  <button type="submit" className="primary-action" disabled={reportBusy || reportDraft.name.trim().length < 1}>
                    <Plus size={16} />
                    Save report
                  </button>
                </div>
              </form>
              <div className="report-card-grid">
                {state.savedReports
                  .filter((report) =>
                    analyticsReportGroup === 'scheduled' ? report.cadence !== 'none' : report.cadence === 'none',
                  )
                  .map((report) => (
                    <article key={report.id} className={report.active ? '' : 'inactive'}>
                      <div>
                        <strong>{report.name}</strong>
                        <span>{report.description || `${titleCase(report.reportType)} report`}</span>
                        {report.recipients.length > 0 ? (
                          <span>Recipients: {report.recipients.join(', ')}</span>
                        ) : null}
                      </div>
                      <em className="chip status-done">{titleCase(report.reportType)}</em>
                      <div className="report-card-actions">
                        <button type="button" onClick={exportAnalyticsRollupsCsv}>
                          <Download size={13} />
                          Export CSV
                        </button>
                        <label className="report-cadence">
                          <span>Schedule</span>
                          <select
                            value={report.cadence}
                            onChange={(event) => void setSavedReportCadence(report, event.target.value)}
                            disabled={reportBusy}
                          >
                            {['none', 'daily', 'weekly', 'monthly'].map((cadence) => (
                              <option key={cadence} value={cadence}>{titleCase(cadence)}</option>
                            ))}
                          </select>
                        </label>
                        <button type="button" disabled={reportBusy} onClick={() => void toggleSavedReport(report)}>
                          {report.active ? 'Pause' : 'Activate'}
                        </button>
                      </div>
                    </article>
                  ))}
                {state.savedReports.filter((report) =>
                  analyticsReportGroup === 'scheduled' ? report.cadence !== 'none' : report.cadence === 'none',
                ).length === 0 ? (
                  <p className="setup-module-hint">
                    {analyticsReportGroup === 'scheduled'
                      ? 'No scheduled exports yet. Save a report and set a schedule.'
                      : 'No saved reports yet. Create one above.'}
                  </p>
                ) : null}
              </div>
            </>
          )}
        </section>
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
        <section className="panel span-2 analytics-rollup-panel">
          <div className="panel-head">
            <div>
              <span>Backend rollups</span>
              <h2>Durable hourly service snapshot</h2>
            </div>
            <DatabaseZap size={20} />
          </div>
          {latestRollup ? (
            <>
              <div className="signal-grid">
                <div><strong>{latestRollup.open_tickets}</strong><span>Open tickets</span></div>
                <div><strong>{latestRollup.at_risk_tickets}</strong><span>At risk</span></div>
                <div><strong>{latestRollup.breached_tickets}</strong><span>Breached</span></div>
                <div><strong>{latestRollup.avg_occupancy}%</strong><span>Occupancy</span></div>
                <div><strong>{latestRollup.avg_csat == null ? 'No data' : latestRollup.avg_csat.toFixed(1)}</strong><span>CSAT</span></div>
              </div>
              <div className="bar-list compact-bars" aria-label="Latest backend channel volume">
                {Object.entries(rollupChannelVolume).map(([channel, value]) => (
                  <div className="bar-row" key={channel}>
                    <span>{titleCase(channel)}</span>
                    <div className="bar-track">
                      <span style={{ width: `${percent(value, maxRollupVolume)}%` }} />
                    </div>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
              <div className="analytics-rollup-list" aria-label="Recent backend analytics rollups">
                {analyticsRollups.slice(0, 5).map((rollup) => (
                  <article key={rollup.id}>
                    <div>
                      <strong>{formatTime(rollup.period_start)}</strong>
                      <span>
                        {rollup.open_tickets} open · {rollup.at_risk_tickets} at risk · {rollup.breached_tickets} breached
                      </span>
                    </div>
                    <em className="chip status-done">{rollup.active_agents} active</em>
                  </article>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state compact">
              <strong>No backend rollups yet</strong>
              <span>The worker will publish hourly dashboard snapshots after the next analytics cycle.</span>
            </div>
          )}
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
            <div><strong>{displayCsat}</strong><span>Average CSAT</span></div>
            <div><strong>{metrics.avgHealth}%</strong><span>Channel health</span></div>
            <div><strong>{metrics.atRisk}</strong><span>At-risk work</span></div>
            <div><strong>{metrics.avgOccupancy}%</strong><span>Occupancy</span></div>
          </div>
          <div className="csat-feedback-list" aria-label="Recent CSAT feedback">
            {csatFeedback.slice(0, 5).map((feedback) => {
              const ticket = state.conversations.find((conversation) => conversation.id === feedback.ticket_id)
              const customer = state.customers.find((item) => item.id === feedback.customer_id)
              return (
                <article key={feedback.id}>
                  <Star size={16} />
                  <div>
                    <strong>{feedback.rating.toFixed(1)} CSAT</strong>
                    <span>
                      {customer?.name ?? feedback.submitted_by ?? 'Customer'} · {ticket?.subject ?? feedback.ticket_id}
                    </span>
                    {feedback.comment ? <p>{feedback.comment}</p> : null}
                  </div>
                </article>
              )
            })}
            {csatFeedback.length === 0 ? (
              <article className="outbound-empty">
                <CheckCircle2 size={16} />
                <div>
                  <strong>No CSAT feedback yet</strong>
                  <span>Customer ratings will appear here after the first submitted survey.</span>
                </div>
              </article>
            ) : null}
          </div>
        </section>
      </div>
    )
  }

  function renderWorkforce() {
    const appointments = [...state.serviceAppointments].sort(
      (a, b) => new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime(),
    )
    const technicians = state.agents
    const statusOptions = ['scheduled', 'en_route', 'in_progress', 'completed', 'cancelled']
    const statusTone: Record<string, string> = {
      scheduled: 'status-pending',
      en_route: 'status-progress',
      in_progress: 'status-progress',
      completed: 'status-done',
      cancelled: 'status-blocked',
    }
    const customerName = (id: string) =>
      state.customers.find((customer) => customer.id === id)?.name ?? 'Unassigned customer'
    const now = Date.now()
    const upcomingCount = appointments.filter(
      (appointment) =>
        new Date(appointment.scheduledAt).getTime() >= now &&
        appointment.status !== 'cancelled' &&
        appointment.status !== 'completed',
    ).length
    const activeCount = appointments.filter(
      (appointment) => appointment.status === 'in_progress' || appointment.status === 'en_route',
    ).length
    const completedCount = appointments.filter((appointment) => appointment.status === 'completed').length

    return (
      <div className="management-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Field service</span>
              <h2>Appointment scheduling and dispatch</h2>
            </div>
            <CalendarClock size={20} />
          </div>
          <div className="workforce-stat-row">
            <article>
              <strong>{appointments.length}</strong>
              <span>Total appointments</span>
            </article>
            <article>
              <strong>{upcomingCount}</strong>
              <span>Upcoming</span>
            </article>
            <article>
              <strong>{activeCount}</strong>
              <span>Active now</span>
            </article>
            <article>
              <strong>{completedCount}</strong>
              <span>Completed</span>
            </article>
          </div>
          <form className="user-create-form canned-response-form" onSubmit={handleCreateServiceAppointment}>
            <div className="canned-form-row">
              <label>
                <span>Appointment title</span>
                <input
                  required
                  value={appointmentDraft.title}
                  onChange={(event) =>
                    setAppointmentDraft((current) => ({ ...current, title: event.target.value }))
                  }
                  placeholder="On-site router replacement"
                  disabled={appointmentBusy}
                />
              </label>
              <label>
                <span>Customer</span>
                <select
                  value={appointmentDraft.customerId}
                  onChange={(event) =>
                    setAppointmentDraft((current) => ({ ...current, customerId: event.target.value }))
                  }
                  disabled={appointmentBusy}
                >
                  <option value="">Select customer</option>
                  {state.customers.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      {customer.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Technician</span>
                <select
                  value={appointmentDraft.technicianId}
                  onChange={(event) =>
                    setAppointmentDraft((current) => ({ ...current, technicianId: event.target.value }))
                  }
                  disabled={appointmentBusy}
                >
                  <option value="">Unassigned</option>
                  {technicians.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="canned-form-row">
              <label>
                <span>Scheduled at</span>
                <input
                  type="datetime-local"
                  required
                  value={appointmentDraft.scheduledAt}
                  onChange={(event) =>
                    setAppointmentDraft((current) => ({ ...current, scheduledAt: event.target.value }))
                  }
                  disabled={appointmentBusy}
                />
              </label>
              <label>
                <span>Duration</span>
                <select
                  value={appointmentDraft.durationMinutes}
                  onChange={(event) =>
                    setAppointmentDraft((current) => ({
                      ...current,
                      durationMinutes: Number(event.target.value),
                    }))
                  }
                  disabled={appointmentBusy}
                >
                  {[30, 60, 90, 120, 180, 240].map((minutes) => (
                    <option key={minutes} value={minutes}>
                      {minutes} minutes
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Location</span>
                <input
                  value={appointmentDraft.location}
                  onChange={(event) =>
                    setAppointmentDraft((current) => ({ ...current, location: event.target.value }))
                  }
                  placeholder="Customer site / address"
                  disabled={appointmentBusy}
                />
              </label>
            </div>
            <label className="canned-form-full">
              <span>Notes</span>
              <textarea
                rows={2}
                value={appointmentDraft.notes}
                onChange={(event) =>
                  setAppointmentDraft((current) => ({ ...current, notes: event.target.value }))
                }
                placeholder="Access instructions, parts required, or context for the technician."
                disabled={appointmentBusy}
              />
            </label>
            <button
              type="submit"
              className="primary-action"
              disabled={
                appointmentBusy ||
                appointmentDraft.title.trim().length < 1 ||
                !appointmentDraft.scheduledAt
              }
            >
              <Plus size={16} />
              Schedule appointment
            </button>
          </form>
        </section>

        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <span>Dispatch board</span>
              <h2>Scheduled service appointments</h2>
            </div>
            <Wrench size={20} />
          </div>
          <div className="workforce-appointment-list">
            {appointments.length === 0 ? (
              <p className="setup-module-hint">
                No service appointments yet. Schedule one above to dispatch a technician.
              </p>
            ) : (
              appointments.map((appointment) => (
                <article className="workforce-appointment-card" key={appointment.id}>
                  <header>
                    <div>
                      <strong>{appointment.title}</strong>
                      <span>{customerName(appointment.customerId)}</span>
                    </div>
                    <em className={`chip ${statusTone[appointment.status] ?? 'status-pending'}`}>
                      {titleCase(appointment.status.replace(/_/g, ' '))}
                    </em>
                  </header>
                  <dl className="workforce-appointment-meta">
                    <div>
                      <dt>When</dt>
                      <dd>{formatTime(appointment.scheduledAt)}</dd>
                    </div>
                    <div>
                      <dt>Duration</dt>
                      <dd>{appointment.durationMinutes} min</dd>
                    </div>
                    <div>
                      <dt>Location</dt>
                      <dd>{appointment.location || '—'}</dd>
                    </div>
                  </dl>
                  {appointment.notes ? (
                    <p className="workforce-appointment-notes">{appointment.notes}</p>
                  ) : null}
                  <div className="workforce-appointment-actions">
                    <label>
                      <span>Technician</span>
                      <select
                        value={appointment.technicianId}
                        onChange={(event) =>
                          void reassignAppointmentTechnician(appointment, event.target.value)
                        }
                        disabled={appointmentBusy}
                      >
                        <option value="">Unassigned</option>
                        {technicians.map((agent) => (
                          <option key={agent.id} value={agent.id}>
                            {agent.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Status</span>
                      <select
                        value={appointment.status}
                        onChange={(event) => void setAppointmentStatus(appointment, event.target.value)}
                        disabled={appointmentBusy}
                      >
                        {statusOptions.map((status) => (
                          <option key={status} value={status}>
                            {titleCase(status.replace(/_/g, ' '))}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </div>
    )
  }

  function renderAdmin() {
    const session = backendSession
    if (!session) return null
    const connectorAccounts = backendSnapshot?.connectorAccounts ?? []
    const outboundMessages = backendSnapshot?.outboundMessages ?? []
    const inboundProviderConfig =
      backendSnapshot?.inboundProviderConfig ?? backendSnapshot?.inbound_provider_config ?? []
    const emailInboundConfig = inboundProviderConfig.find((config) => config.provider === 'email')
    const emailOutboundConfig = outboundProviderConfig.find((config) => config.provider === 'email')
    const failedOutboundMessages = outboundMessages.filter((message) =>
      ['failed', 'retrying', 'dead_lettered'].includes(message.status),
    )
    const platformUsers = backendSnapshot?.users ?? []
    const normalizedUserSearch = userSearch.trim().toLowerCase()
    const visiblePlatformUsers = normalizedUserSearch
      ? platformUsers.filter((user) =>
          [user.name, user.email, user.role, user.permission_profile]
            .join(' ')
            .toLowerCase()
            .includes(normalizedUserSearch),
        )
      : platformUsers
    const activePlatformUsers = platformUsers.filter((user) => user.active)
    const adminPlatformUsers = platformUsers.filter((user) => user.role === 'admin')
    const mfaPlatformUsers = platformUsers.filter((user) => user.mfa_enabled)
    const marketNameById = new Map(availableMarkets.map((market) => [market.id, `${market.code} · ${market.name}`]))
    const canManageUsers = session.user.role === 'admin'
    const canManageEmailSettings = session.user.role === 'admin'
    const canManageIntegrationCredentials = session.user.role === 'admin'
    const canReadAudit = userHasPermission(session.user, 'audit.read')
    const canManageAuditRetention = userHasPermission(session.user, 'setup.manage')
    const canManageAlerts = session.user.role === 'admin' || session.user.role === 'supervisor'
    const criticalAlerts = activeOperationalAlerts.filter((alert) => alert.severity === 'critical')
    const acknowledgedAlerts = activeOperationalAlerts.filter((alert) => alert.status === 'acknowledged')
    const activeAlertDeliveries = alertDeliveries.filter((delivery) => delivery.status !== 'sent')
    const sentAlertDeliveries = alertDeliveries.filter((delivery) => delivery.status === 'sent')
    const backendWriteReady = backendSync.status === 'connected'
    const backendWriteStatus = backendSync.status === 'syncing'
      ? 'Syncing backend writes'
      : backendWriteReady
        ? `Connected to ${backendSync.baseUrl}`
        : backendSync.error || `Waiting to reach ${backendSync.baseUrl}`
    const activeTicketFields = state.ticketFields.filter((field) => field.active)
    const requiredTicketFields = activeTicketFields.filter((field) => field.required)
    const activeSlaPolicies = state.slaPolicies.filter((policy) => policy.active)
    const canManageSlaPolicies = session.user.role === 'admin'
    const setupStats = [
      ['Users', platformUsers.length || 'No sync', `${canManageUsers ? 'Admin access' : 'View only'}`],
      ['Fields', activeTicketFields.length, `${requiredTicketFields.length} required`],
      ['Alerts', activeOperationalAlerts.length, criticalAlerts.length ? `${criticalAlerts.length} critical` : 'No critical'],
      ['Connectors', connectorAccounts.length, `${failedOutboundMessages.length} send issue(s)`],
    ]
    const savedChannelSecretCount = [
      integrationCredentialSettings?.sms_http_auth_token_configured,
      integrationCredentialSettings?.voice_http_auth_token_configured,
      integrationCredentialSettings?.whatsapp_access_token_configured,
      integrationCredentialSettings?.facebook_page_access_token_configured,
      integrationCredentialSettings?.instagram_access_token_configured,
    ].filter(Boolean).length
    const aiAlertReadyCount = [
      integrationCredentialSettings?.anthropic_api_key_configured,
      Boolean(integrationCredentialSettings?.alert_webhook_url),
    ].filter(Boolean).length
    const smsVoiceReadyCount = [
      integrationCredentialSettings?.sms_http_auth_token_configured,
      integrationCredentialSettings?.voice_http_auth_token_configured,
    ].filter(Boolean).length
    const metaReadyCount = [
      integrationCredentialSettings?.whatsapp_access_token_configured,
      integrationCredentialSettings?.facebook_page_access_token_configured,
      integrationCredentialSettings?.instagram_access_token_configured,
    ].filter(Boolean).length
    const peopleStats = [
      ['Active users', activePlatformUsers.length, `${platformUsers.length - activePlatformUsers.length} inactive`],
      ['Admins', adminPlatformUsers.length, 'Can manage setup'],
      ['MFA enabled', mfaPlatformUsers.length, `${platformUsers.length - mfaPlatformUsers.length} pending`],
      ['Groups', state.supportGroups.length, `${state.supportGroups.filter((group) => group.active).length} active`],
    ]
    const activeToolPanel = activeSetupTool ? setupToolPanel[activeSetupTool] : ''
    return (
      <div className="management-grid">
        <section
          id="setup-screen-top"
          className={`panel span-2 setup-panel ${activeSetupTool ? `setup-focused show-${activeToolPanel}` : 'setup-landing'}`}
        >
          <div className="panel-head">
            <div>
              <span>Setup</span>
              <h2>{activeSetupTool ? activeSetupTool : 'Workspace controls'}</h2>
            </div>
            <ShieldCheck size={20} />
          </div>
          <div className="setup-dashboard">
            <div className={`setup-status-strip ${backendWriteReady ? 'ready' : backendSync.status === 'syncing' ? 'syncing' : 'error'}`}>
              {backendWriteReady ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              <span>
                <strong>{backendWriteReady ? 'Backend connected' : 'Backend attention needed'}</strong>
                <small>{backendWriteStatus}</small>
              </span>
              <button className="secondary-action" type="button" onClick={() => refreshBackend()}>
                <RefreshCw size={16} />
                Refresh
              </button>
            </div>
            {!activeSetupTool ? (
              <div className="setup-summary-grid" aria-label="Setup summary">
                {setupStats.map(([label, value, detail]) => (
                  <article key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                    <small>{detail}</small>
                  </article>
                ))}
              </div>
            ) : null}
          </div>
          {activeSetupTool ? (
            <div className="setup-focus-bar">
              <button type="button" className="secondary-action" onClick={closeSetupTool}>
                <ArrowRight className="flip-x" size={15} />
                All tools
              </button>
              <span className="setup-breadcrumb">
                {setupSectionOptions.find((s) => s.id === setupSection)?.label}
                <ChevronDown size={13} className="setup-bc-sep" />
                <strong>{activeSetupTool}</strong>
              </span>
            </div>
          ) : (
            <div className="setup-tool-grid" aria-label="Setup tools">
              {setupSectionOptions.map((section) => {
                const categories = setupModuleCatalog[section.id]
                  .map((category) => ({
                    ...category,
                    modules: category.modules.filter((module) => setupBuiltModules.has(module)),
                  }))
                  .filter((category) => category.modules.length > 0)
                if (categories.length === 0) return null
                return (
                  <div className="setup-tool-group" key={section.id}>
                    <h3>{section.label}</h3>
                    {categories.map((category) => (
                      <div className="setup-tool-cat" key={category.title}>
                        <span>{category.title}</span>
                        <div>
                          {category.modules.map((module) => (
                            <button type="button" key={module} onClick={() => openSetupModule(module)}>
                              <CheckCircle2 size={14} />
                              {module}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              })}
            </div>
          )}
          <div id="setup-section-panels" className="setup-section-anchor" />
          {setupModuleHint ? (
            <p className="setup-module-hint" role="status">
              {setupModuleHint}
            </p>
          ) : null}
          {setupSection === 'forms' ? (
          <>
          <div data-setup-panel="forms-fields" className="automation-settings-panel ticket-fields-panel">
            <div className="panel-head compact">
              <div>
                <span>Ticket forms</span>
                <h2>Fields agents capture</h2>
              </div>
              <ClipboardList size={18} />
            </div>
            <form className="ticket-field-form" onSubmit={handleCreateTicketField}>
              <label>
                <span>Label</span>
                <input
                  required
                  value={ticketFieldDraft.label}
                  onChange={(event) =>
                    setTicketFieldDraft((current) => ({
                      ...current,
                      label: event.target.value,
                      key: current.key || normalizeTicketFieldKey(event.target.value),
                    }))
                  }
                  placeholder="Booking reference"
                />
              </label>
              <label>
                <span>Key</span>
                <input
                  required
                  value={ticketFieldDraft.key}
                  onChange={(event) =>
                    setTicketFieldDraft((current) => ({
                      ...current,
                      key: normalizeTicketFieldKey(event.target.value),
                    }))
                  }
                  placeholder="booking_reference"
                />
              </label>
              <label>
                <span>Type</span>
                <select
                  value={ticketFieldDraft.fieldType}
                  onChange={(event) =>
                    setTicketFieldDraft((current) => ({
                      ...current,
                      fieldType: event.target.value as TicketFieldType,
                    }))
                  }
                >
                  {ticketFieldTypeOptions.map((type) => (
                    <option key={type} value={type}>
                      {titleCase(type)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Position</span>
                <input
                  type="number"
                  min="1"
                  value={ticketFieldDraft.position}
                  onChange={(event) =>
                    setTicketFieldDraft((current) => ({
                      ...current,
                      position: Number(event.target.value || 100),
                    }))
                  }
                />
              </label>
              <label className="span-all">
                <span>Options</span>
                <input
                  value={ticketFieldDraft.options}
                  onChange={(event) =>
                    setTicketFieldDraft((current) => ({ ...current, options: event.target.value }))
                  }
                  placeholder="Booking, Payment, Refund"
                  disabled={!['select', 'multiselect'].includes(ticketFieldDraft.fieldType)}
                />
              </label>
              <div className="ticket-field-channel-picker span-all">
                <span>Channels</span>
                <div>
                  {state.channels
                    .filter((channel) => channel.id !== 'internal')
                    .map((channel) => (
                      <label key={channel.id}>
                        <input
                          type="checkbox"
                          checked={ticketFieldDraft.channels.includes(channel.id)}
                          onChange={() => toggleTicketFieldDraftChannel(channel.id)}
                        />
                        {channel.shortLabel}
                      </label>
                    ))}
                </div>
                <small>Leave all unchecked to show this field on every channel.</small>
              </div>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={ticketFieldDraft.required}
                  onChange={(event) =>
                    setTicketFieldDraft((current) => ({ ...current, required: event.target.checked }))
                  }
                />
                <span>Required</span>
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={ticketFieldDraft.active}
                  onChange={(event) =>
                    setTicketFieldDraft((current) => ({ ...current, active: event.target.checked }))
                  }
                />
                <span>Active</span>
              </label>
              <button className="primary-action" type="submit">
                <Plus size={16} />
                Add field
              </button>
            </form>
            <div className="ticket-field-list" aria-label="Configured ticket fields">
              {state.ticketFields.map((field) => (
                <article key={field.id}>
                  <div>
                    <strong>{field.label}</strong>
                    <span>
                      {field.key} · {titleCase(field.fieldType)} · {field.channels.length ? field.channels.join(', ') : 'All channels'}
                    </span>
                  </div>
                  <em className={`chip status-${field.active ? 'healthy' : 'paused'}`}>
                    {field.active ? 'Active' : 'Paused'}
                  </em>
                  {field.required ? <em className="chip status-risk">Required</em> : null}
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => updateTicketField(field.id, { active: !field.active })}
                  >
                    {field.active ? 'Pause' : 'Activate'}
                  </button>
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => updateTicketField(field.id, { required: !field.required })}
                  >
                    {field.required ? 'Optional' : 'Required'}
                  </button>
                </article>
              ))}
            </div>
          </div>
          <div data-setup-panel="custom-fields" className="automation-settings-panel custom-fields-panel">
            <div className="panel-head compact">
              <div>
                <span>Contact &amp; company fields</span>
                <h2>Custom attributes captured on contacts and companies</h2>
              </div>
              <ClipboardList size={18} />
            </div>
            <div className="people-subtabs" role="tablist" aria-label="Custom field entity">
              {(['contact', 'company'] as const).map((entity) => (
                <button
                  key={entity}
                  type="button"
                  role="tab"
                  aria-selected={customFieldEntity === entity}
                  className={customFieldEntity === entity ? 'active' : ''}
                  onClick={() => setCustomFieldEntity(entity)}
                >
                  {entity === 'contact' ? 'Contact fields' : 'Company fields'}
                </button>
              ))}
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateCustomField}>
              <div className="canned-form-row">
                <label>
                  <span>Field key</span>
                  <input
                    required
                    value={customFieldDraft.key}
                    onChange={(event) => setCustomFieldDraft((current) => ({ ...current, key: event.target.value }))}
                    placeholder="loyalty_tier"
                    disabled={!canManageUsers || customFieldBusy}
                  />
                </label>
                <label>
                  <span>Label</span>
                  <input
                    required
                    value={customFieldDraft.label}
                    onChange={(event) => setCustomFieldDraft((current) => ({ ...current, label: event.target.value }))}
                    placeholder="Loyalty tier"
                    disabled={!canManageUsers || customFieldBusy}
                  />
                </label>
              </div>
              <div className="canned-form-row">
                <label>
                  <span>Type</span>
                  <select
                    value={customFieldDraft.fieldType}
                    onChange={(event) =>
                      setCustomFieldDraft((current) => ({ ...current, fieldType: event.target.value as TicketFieldType }))
                    }
                    disabled={!canManageUsers || customFieldBusy}
                  >
                    {ticketFieldTypeOptions.map((option) => (
                      <option key={option} value={option}>{titleCase(option)}</option>
                    ))}
                  </select>
                </label>
                <label className="custom-field-required">
                  <input
                    type="checkbox"
                    checked={customFieldDraft.required}
                    onChange={(event) => setCustomFieldDraft((current) => ({ ...current, required: event.target.checked }))}
                    disabled={!canManageUsers || customFieldBusy}
                  />
                  <span>Required</span>
                </label>
              </div>
              {customFieldDraft.fieldType === 'select' || customFieldDraft.fieldType === 'multiselect' ? (
                <label>
                  <span>Options (comma separated)</span>
                  <input
                    value={customFieldDraft.options}
                    onChange={(event) => setCustomFieldDraft((current) => ({ ...current, options: event.target.value }))}
                    placeholder="Blue, Silver, Gold"
                    disabled={!canManageUsers || customFieldBusy}
                  />
                </label>
              ) : null}
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || customFieldBusy || customFieldDraft.label.trim().length < 1}
              >
                <Plus size={16} />
                Add {customFieldEntity} field
              </button>
            </form>
            <div className="canned-response-list">
              {state.customFieldDefinitions.filter((field) => field.entity === customFieldEntity).length === 0 ? (
                <p className="setup-module-hint">No {customFieldEntity} fields yet. Add one above.</p>
              ) : (
                state.customFieldDefinitions
                  .filter((field) => field.entity === customFieldEntity)
                  .map((field) => (
                    <article className={`canned-response-card ${field.active ? '' : 'inactive'}`} key={field.id}>
                      <div className="canned-card-head">
                        <div>
                          <strong>{field.label}</strong>
                          <span className="template-priority">{titleCase(field.fieldType)}</span>
                          {field.required ? <span className="template-priority priority-high">Required</span> : null}
                        </div>
                        <span><code>{field.key}</code></span>
                      </div>
                      {field.options.length > 0 ? (
                        <div className="tag-list compact-tags">
                          {field.options.map((option) => (
                            <span key={option}>{option}</span>
                          ))}
                        </div>
                      ) : null}
                      <div className="canned-card-actions">
                        <button
                          type="button"
                          className="secondary-action"
                          disabled={!canManageUsers || customFieldBusy}
                          onClick={() => void toggleCustomField(field)}
                        >
                          {field.active ? 'Pause' : 'Activate'}
                        </button>
                      </div>
                    </article>
                  ))
              )}
            </div>
          </div>
          <div data-setup-panel="custom-objects" className="automation-settings-panel custom-objects-panel">
            <div className="panel-head compact">
              <div>
                <span>Custom objects</span>
                <h2>Reusable object schemas with typed fields</h2>
              </div>
              <DatabaseZap size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateCustomObject}>
              <div className="canned-form-row">
                <label>
                  <span>Key</span>
                  <input
                    required
                    value={objectDraft.key}
                    onChange={(event) => setObjectDraft((current) => ({ ...current, key: event.target.value }))}
                    placeholder="loyalty_account"
                    disabled={!canManageUsers || objectBusy}
                  />
                </label>
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={objectDraft.name}
                    onChange={(event) => setObjectDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Loyalty account"
                    disabled={!canManageUsers || objectBusy}
                  />
                </label>
              </div>
              <label>
                <span>Description</span>
                <input
                  value={objectDraft.description}
                  onChange={(event) => setObjectDraft((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Frequent-flyer account linked to a traveller"
                  disabled={!canManageUsers || objectBusy}
                />
              </label>
              <div className="scenario-action-builder">
                <span className="scenario-builder-label">Fields</span>
                {objectFields.length > 0 ? (
                  <ul className="scenario-action-list">
                    {objectFields.map((field, index) => (
                      <li key={`${field.key}-${index}`}>
                        <span>{field.label} (<b>{titleCase(field.fieldType)}</b>) · {field.key}</span>
                        <button type="button" aria-label="Remove field" onClick={() => removeObjectField(index)}>
                          <X size={13} />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <div className="scenario-action-row">
                  <input
                    value={objectFieldDraft.key}
                    onChange={(event) => setObjectFieldDraft((current) => ({ ...current, key: event.target.value }))}
                    placeholder="field_key"
                    disabled={!canManageUsers || objectBusy}
                    aria-label="Field key"
                  />
                  <input
                    value={objectFieldDraft.label}
                    onChange={(event) => setObjectFieldDraft((current) => ({ ...current, label: event.target.value }))}
                    placeholder="Field label"
                    disabled={!canManageUsers || objectBusy}
                    aria-label="Field label"
                  />
                  <select
                    value={objectFieldDraft.fieldType}
                    onChange={(event) =>
                      setObjectFieldDraft((current) => ({ ...current, fieldType: event.target.value as TicketFieldType }))
                    }
                    disabled={!canManageUsers || objectBusy}
                    aria-label="Field type"
                  >
                    {ticketFieldTypeOptions.map((option) => (
                      <option key={option} value={option}>{titleCase(option)}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="secondary-action"
                    onClick={addObjectField}
                    disabled={!canManageUsers || objectBusy || !/^[a-z][a-z0-9_]{1,63}$/.test(objectFieldDraft.key.trim().toLowerCase())}
                  >
                    <Plus size={14} />
                    Add field
                  </button>
                </div>
              </div>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || objectBusy || objectDraft.name.trim().length < 1 || !/^[a-z][a-z0-9_]{1,63}$/.test(objectDraft.key.trim().toLowerCase())}
              >
                <Plus size={16} />
                Add object
              </button>
            </form>
            <div className="canned-response-list">
              {state.customObjects.length === 0 ? (
                <p className="setup-module-hint">No custom objects yet. Define one above.</p>
              ) : (
                state.customObjects.map((object) => (
                  <article className={`canned-response-card ${object.active ? '' : 'inactive'}`} key={object.id}>
                    <div className="canned-card-head">
                      <div>
                        <strong>{object.name}</strong>
                        <span className="template-priority">{object.fields.length} fields</span>
                      </div>
                      <span><code>{object.key}</code></span>
                    </div>
                    {object.description ? <p className="canned-card-body">{object.description}</p> : null}
                    {object.fields.length > 0 ? (
                      <div className="tag-list compact-tags">
                        {object.fields.map((field) => (
                          <span key={field.key}>{field.label}: {titleCase(field.fieldType)}</span>
                        ))}
                      </div>
                    ) : null}
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || objectBusy}
                        onClick={() => void toggleCustomObject(object)}
                      >
                        {object.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
          <div data-setup-panel="products" className="automation-settings-panel products-panel">
            <div className="panel-head compact">
              <div>
                <span>Products</span>
                <h2>Multiple products tickets can be filed against</h2>
              </div>
              <BookOpen size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateProduct}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={productDraft.name}
                    onChange={(event) => setProductDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Wakanow Tours"
                    disabled={!canManageUsers || productBusy}
                  />
                </label>
                <label>
                  <span>Code</span>
                  <input
                    value={productDraft.code}
                    onChange={(event) => setProductDraft((current) => ({ ...current, code: event.target.value }))}
                    placeholder="TOURS"
                    disabled={!canManageUsers || productBusy}
                  />
                </label>
              </div>
              <label>
                <span>Description</span>
                <input
                  value={productDraft.description}
                  onChange={(event) => setProductDraft((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Guided tours and experiences"
                  disabled={!canManageUsers || productBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || productBusy || productDraft.name.trim().length < 1}
              >
                <Plus size={16} />
                Add product
              </button>
            </form>
            <div className="canned-response-list">
              {state.products.length === 0 ? (
                <p className="setup-module-hint">No products yet. Add the products you support.</p>
              ) : (
                state.products.map((product) => (
                  <article className={`canned-response-card ${product.active ? '' : 'inactive'}`} key={product.id}>
                    <div className="canned-card-head">
                      <div>
                        <strong>{product.name}</strong>
                        {product.code ? <code>{product.code}</code> : null}
                      </div>
                    </div>
                    {product.description ? <p className="canned-card-body">{product.description}</p> : null}
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || productBusy}
                        onClick={() => void toggleProduct(product)}
                      >
                        {product.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
          <div data-setup-panel="branding" className="automation-settings-panel branding-settings-panel" id="portal-branding">
            <div className="panel-head compact">
              <div>
                <span>Portal branding</span>
                <h2>Customer help center & helpdesk identity</h2>
              </div>
              <Globe2 size={18} />
            </div>
            {workspaceSettings ? (
              <form className="sso-settings-form" onSubmit={handleBrandingSave}>
                <div className="sso-settings-grid">
                  <label>
                    <span>Brand name</span>
                    <input
                      value={brandingDraft.publicBrandName}
                      onChange={(event) =>
                        setBrandingDraft((current) => ({ ...current, publicBrandName: event.target.value }))
                      }
                      placeholder="Omni Ticket"
                      disabled={brandingBusy}
                    />
                  </label>
                  <label>
                    <span>Support team name</span>
                    <input
                      value={brandingDraft.portalSupportName}
                      onChange={(event) =>
                        setBrandingDraft((current) => ({ ...current, portalSupportName: event.target.value }))
                      }
                      placeholder="Omni Ticket Support"
                      disabled={brandingBusy}
                    />
                  </label>
                  <label>
                    <span>Logo URL</span>
                    <input
                      value={brandingDraft.portalLogoUrl}
                      onChange={(event) =>
                        setBrandingDraft((current) => ({ ...current, portalLogoUrl: event.target.value }))
                      }
                      placeholder="https://cdn.example.com/logo.svg"
                      disabled={brandingBusy}
                    />
                  </label>
                  <label>
                    <span>Primary color</span>
                    <input
                      type="color"
                      value={brandingDraft.portalPrimaryColor}
                      onChange={(event) =>
                        setBrandingDraft((current) => ({ ...current, portalPrimaryColor: event.target.value }))
                      }
                      disabled={brandingBusy}
                    />
                  </label>
                </div>
                <label className="sso-settings-full">
                  <span>Help center welcome message</span>
                  <textarea
                    rows={2}
                    value={brandingDraft.portalWelcomeMessage}
                    onChange={(event) =>
                      setBrandingDraft((current) => ({ ...current, portalWelcomeMessage: event.target.value }))
                    }
                    placeholder="Search our help center or open a ticket — our support team replies fast."
                    disabled={brandingBusy}
                  />
                </label>
                <button type="submit" className="primary-action" disabled={brandingBusy}>
                  <Globe2 size={16} />
                  Save branding
                </button>
              </form>
            ) : (
              <p className="setup-module-hint">Sign in as an administrator to manage portal branding.</p>
            )}
          </div>
          </>
          ) : null}
          {setupSection === 'governance' ? (
          <>
          <div data-setup-panel="forums" className="automation-settings-panel forums-panel" id="forums">
            <div className="panel-head compact">
              <div>
                <span>Community forums</span>
                <h2>Discussion topics & staff answers</h2>
              </div>
              <button
                type="button"
                className="primary-action"
                aria-expanded={forumOpen}
                onClick={() => setForumOpen((open) => !open)}
              >
                <Plus size={16} />
                New topic
              </button>
            </div>
            {forumOpen ? (
              <form className="user-create-form canned-response-form" onSubmit={handleCreateForumTopic}>
                <div className="canned-form-row">
                  <label>
                    <span>Title</span>
                    <input
                      required
                      value={forumDraft.title}
                      onChange={(event) => setForumDraft((current) => ({ ...current, title: event.target.value }))}
                      placeholder="How do refunds work for partial cancellations?"
                      disabled={forumBusy}
                    />
                  </label>
                  <label>
                    <span>Category</span>
                    <input
                      value={forumDraft.category}
                      onChange={(event) => setForumDraft((current) => ({ ...current, category: event.target.value }))}
                      placeholder="Billing & refunds"
                      disabled={forumBusy}
                    />
                  </label>
                </div>
                <label className="canned-form-full">
                  <span>Body</span>
                  <textarea
                    rows={2}
                    value={forumDraft.body}
                    onChange={(event) => setForumDraft((current) => ({ ...current, body: event.target.value }))}
                    placeholder="Describe the discussion or question for the team."
                    disabled={forumBusy}
                  />
                </label>
                <button
                  type="submit"
                  className="primary-action"
                  disabled={forumBusy || forumDraft.title.trim().length < 2}
                >
                  <Plus size={16} />
                  Create topic
                </button>
              </form>
            ) : null}
            {state.discussionTopics.length === 0 ? (
              <p className="setup-module-hint">No discussion topics yet. Start one to share answers with the team.</p>
            ) : (
              <div className="forum-topic-list">
                {state.discussionTopics.map((topic) => (
                  <article className="forum-topic-card" key={topic.id}>
                    <header>
                      <div>
                        <strong>
                          {topic.pinned ? <Star size={13} className="forum-pin" /> : null}
                          {topic.title}
                        </strong>
                        <span>
                          {topic.category} · {topic.author || 'Staff'} · {topic.replyCount} repl
                          {topic.replyCount === 1 ? 'y' : 'ies'} · Updated {formatTime(topic.updatedAt)}
                        </span>
                      </div>
                      <em
                        className={`chip status-${
                          topic.status === 'answered' ? 'done' : topic.status === 'closed' ? 'blocked' : 'pending'
                        }`}
                      >
                        {titleCase(topic.status)}
                      </em>
                    </header>
                    {topic.body ? <p className="forum-topic-body">{topic.body}</p> : null}
                    <div className="forum-topic-actions">
                      <label>
                        <span>Status</span>
                        <select
                          value={topic.status}
                          onChange={(event) => void setForumTopicStatus(topic, event.target.value)}
                          disabled={forumBusy}
                        >
                          {['open', 'answered', 'closed'].map((status) => (
                            <option key={status} value={status}>
                              {titleCase(status)}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button type="button" disabled={forumBusy} onClick={() => void toggleForumTopicPin(topic)}>
                        {topic.pinned ? 'Unpin' : 'Pin'}
                      </button>
                      <button type="button" onClick={() => void toggleForumTopicComments(topic)}>
                        {expandedTopicId === topic.id ? 'Hide replies' : 'View replies'}
                      </button>
                    </div>
                    {expandedTopicId === topic.id ? (
                      <div className="forum-comment-thread">
                        {topicCommentsBusy && topicComments.length === 0 ? (
                          <p className="setup-module-hint">Loading replies…</p>
                        ) : topicComments.length === 0 ? (
                          <p className="setup-module-hint">No replies yet. Be the first to answer.</p>
                        ) : (
                          topicComments.map((comment) => (
                            <div className="forum-comment" key={comment.id}>
                              <strong>{comment.author || 'Staff'}</strong>
                              <span>{formatTime(comment.created_at)}</span>
                              <p>{comment.body}</p>
                            </div>
                          ))
                        )}
                        <form className="forum-comment-form" onSubmit={(event) => void handleAddForumComment(event, topic)}>
                          <input
                            value={commentDraft}
                            onChange={(event) => setCommentDraft(event.target.value)}
                            placeholder="Write a reply…"
                            disabled={topicCommentsBusy}
                          />
                          <button
                            type="submit"
                            className="primary-action"
                            disabled={topicCommentsBusy || commentDraft.trim().length < 1}
                          >
                            <Send size={14} />
                            Reply
                          </button>
                        </form>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
          </div>
          <div data-setup-panel="audit" className="automation-settings-panel audit-governance-panel" id="audit-controls">
            <div className="panel-head compact">
              <div>
                <span>Audit governance</span>
                <h2>Export and retention</h2>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="operational-alert-summary-grid" aria-label="Audit retention summary">
              {[
                ['Visible events', auditRetention?.retained_events ?? 0],
                ['Prunable', auditRetention?.prunable_events ?? 0],
                ['Retention days', auditRetention?.retention_days ?? 0],
                ['Export cap', auditRetention?.export_max_rows ?? 0],
              ].map(([label, value]) => (
                <article key={label}>
                  <strong>{value}</strong>
                  <span>{label}</span>
                </article>
              ))}
            </div>
            <div className="alert-delivery-config" aria-label="Audit export and retention policy">
              <article>
                <DatabaseZap size={16} />
                <span>
                  <strong>Retention cutoff</strong>
                  <small>
                    {auditRetention
                      ? `Events older than ${formatTime(auditRetention.cutoff_at)} are eligible for pruning.`
                      : canReadAudit
                        ? 'Loading the active audit retention policy.'
                        : 'Audit visibility requires the audit.read permission.'}
                  </small>
                </span>
              </article>
              <article>
                <Download size={16} />
                <span>
                  <strong>Export scope</strong>
                  <small>Exports include global events and the active market only.</small>
                </span>
              </article>
            </div>
            <div className="operational-alert-actions audit-actions">
              <button
                className="secondary-action"
                type="button"
                onClick={() => void handleAuditExport('csv')}
                disabled={!canReadAudit || auditActionBusy}
              >
                <Download size={15} />
                Export CSV
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() => void handleAuditExport('json')}
                disabled={!canReadAudit || auditActionBusy}
              >
                <Code2 size={15} />
                Export JSON
              </button>
              <button
                className="primary-action"
                type="button"
                onClick={() => void handleAuditPrune()}
                disabled={!canManageAuditRetention || auditActionBusy || (auditRetention?.prunable_events ?? 0) === 0}
              >
                <DatabaseZap size={15} />
                Run retention
              </button>
            </div>
          </div>
          <div data-setup-panel="attachment" className="automation-settings-panel attachment-governance-panel" id="attachment-controls">
            <div className="panel-head compact">
              <div>
                <span>Attachment governance</span>
                <h2>Storage lifecycle</h2>
              </div>
              <Paperclip size={18} />
            </div>
            <div className="operational-alert-summary-grid" aria-label="Attachment retention summary">
              {[
                ['Active', attachmentRetention?.active_attachments ?? 0],
                ['Deleted', attachmentRetention?.deleted_attachments ?? 0],
                ['Purged', attachmentRetention?.purged_attachments ?? 0],
                ['Purgeable', attachmentRetention?.purgeable_attachments ?? 0],
              ].map(([label, value]) => (
                <article key={label}>
                  <strong>{value}</strong>
                  <span>{label}</span>
                </article>
              ))}
            </div>
            <div className="alert-delivery-config" aria-label="Attachment storage lifecycle policy">
              <article>
                <DatabaseZap size={16} />
                <span>
                  <strong>Active retention</strong>
                  <small>
                    {attachmentRetention
                      ? `${attachmentRetention.active_retention_days} days · cutoff ${formatTime(attachmentRetention.active_cutoff_at)}.`
                      : 'Loading the active attachment retention policy.'}
                  </small>
                </span>
              </article>
              <article>
                <Paperclip size={16} />
                <span>
                  <strong>Deleted retention</strong>
                  <small>
                    {attachmentRetention
                      ? `${attachmentRetention.deleted_retention_days} days before stored bytes are purged.`
                      : 'Purged metadata remains available for audit history.'}
                  </small>
                </span>
              </article>
            </div>
            <div className="outbound-provider-grid attachment-provider-grid" aria-label="Attachment provider readiness">
              <article>
                <div className="outbound-provider-head">
                  <span className={`channel-health-dot ${attachmentProviderConfig?.storage_live ? 'healthy' : 'degraded'}`} />
                  <div>
                    <strong>Attachment storage</strong>
                    <small>
                      {attachmentProviderConfig
                        ? attachmentProviderConfig.notes
                        : 'Storage provider readiness is available to supervisors and admins.'}
                    </small>
                  </div>
                  <em className={`chip status-${attachmentProviderConfig?.storage_live ? 'done' : 'pending'}`}>
                    {attachmentProviderConfig?.storage_live ? 'Live' : 'Pending'}
                  </em>
                </div>
                <div className="outbound-provider-meta">
                  <span>
                    <b>Backend</b>
                    {titleCase(attachmentProviderConfig?.storage_backend ?? 'local')}
                  </span>
                  <span>
                    <b>Scanner</b>
                    {titleCase(attachmentProviderConfig?.scanner_adapter ?? 'local')}
                  </span>
                  <span>
                    <b>Missing</b>
                    {attachmentProviderConfig?.missing_settings.length ?? 0}
                  </span>
                </div>
                {attachmentProviderConfig?.missing_settings.length ? (
                  <div className="connector-needed">
                    <AlertTriangle size={15} />
                    <span>{attachmentProviderConfig.missing_settings.slice(0, 2).join(' · ')}</span>
                  </div>
                ) : null}
              </article>
            </div>
            <div className="operational-alert-actions audit-actions">
              <button
                className="primary-action"
                type="button"
                onClick={() => void handleAttachmentPrune()}
                disabled={
                  !canManageAuditRetention ||
                  attachmentActionBusy ||
                  (attachmentRetention?.purgeable_attachments ?? 0) === 0
                }
              >
                <DatabaseZap size={15} />
                Run attachment retention
              </button>
            </div>
          </div>
          </>
          ) : null}
          {setupSection === 'people' ? (
          <div data-setup-panel="people" className="automation-settings-panel user-management-panel people-workspace">
            <div className="panel-head compact people-workspace-head">
              <div>
                <span>People management</span>
                <h2>Users, roles, and markets</h2>
              </div>
              <div className="people-head-actions">
                <button className="secondary-action" type="button" onClick={() => refreshBackend()}>
                  <RefreshCw size={16} />
                  Refresh
                </button>
                <button
                  className="primary-action"
                  type="button"
                  onClick={() => {
                    setPeopleView('users')
                    setAddUserOpen(true)
                  }}
                  disabled={!canManageUsers}
                >
                  <Plus size={16} />
                  Add user
                </button>
              </div>
            </div>
            <div className={`setup-status-strip ${backendWriteReady ? 'ready' : backendSync.status === 'syncing' ? 'syncing' : 'error'}`}>
              {backendWriteReady ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              <span>
                <strong>Backend writes</strong>
                <small>{backendWriteStatus}</small>
              </span>
            </div>
            <div className="people-summary-grid" aria-label="People summary">
              {peopleStats.map(([label, value, detail]) => (
                <article key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{detail}</small>
                </article>
              ))}
            </div>
            <div className="people-subtabs" role="tablist" aria-label="People sections">
              {[
                { id: 'users' as const, label: 'Users', icon: Users },
                { id: 'groups' as const, label: 'Groups', icon: Building2 },
                { id: 'hours' as const, label: 'Business hours', icon: Clock },
                { id: 'security' as const, label: 'Security', icon: ShieldCheck },
              ].map(({ id, label, icon: SectionIcon }) => {
                return (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={peopleView === id}
                    className={peopleView === id ? 'active' : ''}
                    onClick={() => setPeopleView(id)}
                  >
                    <SectionIcon size={15} />
                    {label}
                  </button>
                )
              })}
            </div>

            {peopleView === 'users' ? (
              <section className="people-section" aria-label="Users">
                <div className="people-toolbar">
                  <label className="global-search people-search">
                    <Search size={16} />
                    <input
                      value={userSearch}
                      onChange={(event) => setUserSearch(event.target.value)}
                      placeholder="Search users"
                      aria-label="Search users"
                    />
                  </label>
                  <button
                    className={addUserOpen ? 'secondary-action' : 'primary-action'}
                    type="button"
                    onClick={() => setAddUserOpen((value) => !value)}
                    disabled={!canManageUsers}
                    aria-expanded={addUserOpen}
                  >
                    {addUserOpen ? <X size={16} /> : <Plus size={16} />}
                    {addUserOpen ? 'Close form' : 'Add user'}
                  </button>
                </div>
                {addUserOpen ? (
                  <form className="user-create-form people-add-form" onSubmit={handleCreateUser}>
                    <label>
                      <span>Name</span>
                      <input
                        required
                        value={newUser.name}
                        onChange={(event) => setNewUser((current) => ({ ...current, name: event.target.value }))}
                        placeholder="Agent name"
                        disabled={!canManageUsers || userActionBusy}
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
                        disabled={!canManageUsers || userActionBusy}
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
                        disabled={!canManageUsers || userActionBusy}
                      >
                        {userRoleOptions.map((role) => (
                          <option key={role} value={role}>
                            {titleCase(role)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Permission profile</span>
                      <select
                        value={newUser.permissionProfile}
                        onChange={(event) =>
                          setNewUser((current) => ({
                            ...current,
                            permissionProfile: event.target.value as BackendPermissionProfile,
                          }))
                        }
                        disabled={!canManageUsers || userActionBusy}
                      >
                        {permissionProfileOptions.map((profile) => (
                          <option key={profile} value={profile}>
                            {titleCase(profile)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Temporary password</span>
                      <input
                        required
                        minLength={8}
                        type="password"
                        value={newUser.temporaryPassword}
                        onChange={(event) =>
                          setNewUser((current) => ({
                            ...current,
                            temporaryPassword: event.target.value,
                          }))
                        }
                        placeholder="Minimum 8 characters"
                        disabled={!canManageUsers || userActionBusy}
                      />
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
                        disabled={!canManageUsers || userActionBusy}
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
                              disabled={!canManageUsers || userActionBusy}
                            />
                            {market.code}
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="form-actions">
                      <button className="secondary-action" type="button" onClick={() => setAddUserOpen(false)}>
                        Cancel
                      </button>
                      <button className="primary-action" type="submit" disabled={!canManageUsers || userActionBusy}>
                        <Plus size={16} />
                        {userActionBusy ? 'Saving...' : 'Add user'}
                      </button>
                    </div>
                  </form>
                ) : null}
                <div className="user-list" aria-label="Backend users">
                  {visiblePlatformUsers.map((user) => (
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
                        {user.password_reset_required ? (
                          <em className="chip status-risk">Password reset required</em>
                        ) : null}
                        {user.mfa_enabled ? <em className="chip status-healthy">MFA</em> : null}
                      </div>
                      <div className="user-security-row">
                        <span>
                          Last login {user.last_login_at ? formatTime(user.last_login_at) : 'not recorded'}
                        </span>
                        <span>
                          MFA {user.mfa_enabled ? 'enabled' : 'off'}
                        </span>
                        <span>
                          Permissions {userPermissionCount(user)}
                        </span>
                      </div>
                      <details className="user-card-details">
                        <summary>
                          <span>Manage access</span>
                          <ChevronDown size={15} />
                        </summary>
                        <div className="user-card-details-body">
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
                                disabled={!canManageUsers || userActionBusy}
                              >
                                {userRoleOptions.map((role) => (
                                  <option key={role} value={role}>
                                    {titleCase(role)}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              <span>Permission profile</span>
                              <select
                                value={user.permission_profile}
                                onChange={(event) =>
                                  updateUser(user.id, {
                                    permission_profile: event.target.value as BackendPermissionProfile,
                                  })
                                }
                                disabled={!canManageUsers || userActionBusy}
                              >
                                {permissionProfileOptions.map((profile) => (
                                  <option key={profile} value={profile}>
                                    {titleCase(profile)}
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
                                disabled={!canManageUsers || userActionBusy}
                              >
                                {availableMarkets.map((market) => (
                                  <option key={market.id} value={market.id}>
                                    {market.code}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <div className="permission-summary" aria-label={`${user.name} effective permissions`}>
                              {permissionOptions.map((permission) => (
                                <em
                                  className={`chip status-${userHasPermission(user, permission.value) ? 'healthy' : 'paused'}`}
                                  key={permission.value}
                                >
                                  {permission.label}
                                </em>
                              ))}
                            </div>
                            <div className="permission-override-grid" aria-label={`${user.name} permission overrides`}>
                              {permissionOptions.map((permission) => {
                                const mode = user.permission_overrides.allow.includes(permission.value)
                                  ? 'allow'
                                  : user.permission_overrides.deny.includes(permission.value)
                                    ? 'deny'
                                    : 'default'
                                return (
                                  <label key={permission.value}>
                                    <span>{permission.label}</span>
                                    <select
                                      value={mode}
                                      onChange={(event) =>
                                        updateUserPermissionOverride(
                                          user,
                                          permission.value,
                                          event.target.value as 'default' | 'allow' | 'deny',
                                        )
                                      }
                                      disabled={!canManageUsers || userActionBusy}
                                    >
                                      <option value="default">Default</option>
                                      <option value="allow">Allow</option>
                                      <option value="deny">Deny</option>
                                    </select>
                                  </label>
                                )
                              })}
                            </div>
                            <button
                              className="secondary-action"
                              type="button"
                              onClick={() => updateUser(user.id, { active: !user.active })}
                              disabled={!canManageUsers || userActionBusy || user.id === backendSession?.user.id}
                            >
                              {user.active ? 'Deactivate' : 'Reactivate'}
                            </button>
                          </div>
                          <div className="user-card-controls password-reset-controls">
                            <label>
                              <span>Reset password</span>
                              <input
                                minLength={8}
                                type="password"
                                value={passwordResetDrafts[user.id] ?? ''}
                                onChange={(event) =>
                                  setPasswordResetDrafts((current) => ({
                                    ...current,
                                    [user.id]: event.target.value,
                                  }))
                                }
                                placeholder="New temporary password"
                                disabled={!canManageUsers || userActionBusy}
                              />
                            </label>
                            <button
                              className="secondary-action"
                              type="button"
                              onClick={async () => {
                                const temporaryPassword = (passwordResetDrafts[user.id] ?? '').trim()
                                if (temporaryPassword.length < 8) return
                                setUserActionBusy(true)
                                try {
                                  const saved = await updateUser(user.id, { temporary_password: temporaryPassword })
                                  if (saved) {
                                    setPasswordResetDrafts((current) => ({ ...current, [user.id]: '' }))
                                    setPrototypeNotice(`Temporary password reset for ${user.name}.`)
                                  }
                                } finally {
                                  setUserActionBusy(false)
                                }
                              }}
                              disabled={!canManageUsers || userActionBusy || (passwordResetDrafts[user.id] ?? '').trim().length < 8}
                            >
                              Reset
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
                                    disabled={!canManageUsers || userActionBusy}
                                  />
                                  {marketNameById.get(market.id) ?? market.id}
                                </label>
                              )
                            })}
                          </div>
                        </div>
                      </details>
                    </article>
                  ))}
                  {platformUsers.length === 0 ? (
                    <article className="user-card empty">
                      <strong>No backend users loaded</strong>
                      <span>Refresh backend sync after the API starts.</span>
                    </article>
                  ) : null}
                  {platformUsers.length > 0 && visiblePlatformUsers.length === 0 ? (
                    <article className="user-card empty">
                      <strong>No matching users</strong>
                      <span>Clear the search field to see everyone.</span>
                    </article>
                  ) : null}
                </div>
              </section>
            ) : null}

            {peopleView === 'groups' ? (
              <section className="people-section support-group-panel" aria-label="Support groups">
                <div className="support-group-head">
                  <div>
                    <span>Support groups</span>
                    <h3>Team ownership and routing</h3>
                  </div>
                  <button
                    className={addGroupOpen ? 'secondary-action' : 'primary-action'}
                    type="button"
                    onClick={() => setAddGroupOpen((value) => !value)}
                    disabled={!canManageUsers}
                    aria-expanded={addGroupOpen}
                  >
                    {addGroupOpen ? <X size={16} /> : <Plus size={16} />}
                    {addGroupOpen ? 'Close form' : 'Add group'}
                  </button>
                </div>
                {addGroupOpen ? (
                  <form className="user-create-form support-group-form" onSubmit={handleCreateSupportGroup}>
                    <label>
                      <span>Group name</span>
                      <input
                        required
                        value={supportGroupDraft.name}
                        onChange={(event) =>
                          setSupportGroupDraft((current) => ({ ...current, name: event.target.value }))
                        }
                        placeholder="Refund Desk"
                        disabled={!canManageUsers || groupActionBusy}
                      />
                    </label>
                    <label>
                      <span>Description</span>
                      <input
                        value={supportGroupDraft.description}
                        onChange={(event) =>
                          setSupportGroupDraft((current) => ({ ...current, description: event.target.value }))
                        }
                        placeholder="What this team owns"
                        disabled={!canManageUsers || groupActionBusy}
                      />
                    </label>
                    <label>
                      <span>Team inbox (per-function email)</span>
                      <input
                        type="email"
                        value={supportGroupDraft.teamEmail}
                        onChange={(event) =>
                          setSupportGroupDraft((current) => ({ ...current, teamEmail: event.target.value }))
                        }
                        placeholder="refunds@wakanow.com"
                        disabled={!canManageUsers || groupActionBusy}
                      />
                      <small className="field-hint">
                        Email to this address routes to this team; replies send from it. The shared
                        mailbox transport is set in Setup → Connectors → Email.
                      </small>
                    </label>
                    <label>
                      <span>Skills</span>
                      <input
                        value={supportGroupDraft.skills}
                        onChange={(event) =>
                          setSupportGroupDraft((current) => ({ ...current, skills: event.target.value }))
                        }
                        placeholder="refunds, payments"
                        disabled={!canManageUsers || groupActionBusy}
                      />
                    </label>
                    <div className="user-market-picker" aria-label="Support group channels">
                      <span>Channels</span>
                      <div>
                        {state.channels.slice(0, 8).map((channel) => (
                          <label key={channel.id}>
                            <input
                              type="checkbox"
                              checked={supportGroupDraft.channels.includes(channel.id)}
                              onChange={() => toggleSupportGroupDraftChannel(channel.id)}
                              disabled={!canManageUsers || groupActionBusy}
                            />
                            {channel.shortLabel}
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="form-actions">
                      <button className="secondary-action" type="button" onClick={() => setAddGroupOpen(false)}>
                        Cancel
                      </button>
                      <button className="primary-action" type="submit" disabled={!canManageUsers || groupActionBusy}>
                        <Plus size={16} />
                        {groupActionBusy ? 'Saving...' : 'Add group'}
                      </button>
                    </div>
                  </form>
                ) : null}
                <div className="support-group-grid">
                  {state.supportGroups.map((group) => (
                    <article className={group.active ? 'support-group-card' : 'support-group-card paused'} key={group.id}>
                      <div>
                        <strong>{group.name}</strong>
                        <span>{group.description || 'No description yet.'}</span>
                        <span>{group.teamEmail || 'No team inbox set'}</span>
                      </div>
                      <div className="support-group-metrics">
                        <span><b>{group.memberCount}</b> members</span>
                        <span><b>{group.openTicketCount}</b> open</span>
                        <span><b>{group.slaRiskCount}</b> risk</span>
                      </div>
                      <div className="tag-list compact-tags">
                        {group.channels.slice(0, 4).map((channel) => (
                          <span key={channel}>{titleCase(channel)}</span>
                        ))}
                      </div>
                      <button
                        className="secondary-action"
                        type="button"
                        onClick={() => void handleToggleSupportGroup(group.id, !group.active)}
                        disabled={!canManageUsers || groupActionBusy}
                      >
                        {group.active ? 'Pause' : 'Reactivate'}
                      </button>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {peopleView === 'hours' ? (
              <section className="people-section business-hours-panel" aria-label="Business hours">
                <div className="support-group-head">
                  <div>
                    <span>Business hours</span>
                    <h3>Operating calendars used by SLA timers</h3>
                  </div>
                </div>
                <form className="user-create-form business-hours-form" onSubmit={handleCreateBusinessHours}>
                  <label>
                    <span>Calendar name</span>
                    <input
                      required
                      value={businessHoursName}
                      onChange={(event) => setBusinessHoursName(event.target.value)}
                      placeholder="Weekend support hours"
                      disabled={!canManageUsers}
                    />
                  </label>
                  <label>
                    <span>Time zone</span>
                    <input
                      value={businessHoursTimezone}
                      onChange={(event) => setBusinessHoursTimezone(event.target.value)}
                      placeholder="Africa/Lagos"
                      disabled={!canManageUsers}
                    />
                  </label>
                  <button
                    type="submit"
                    className="primary-action"
                    disabled={!canManageUsers || businessHoursName.trim().length < 2}
                  >
                    <Plus size={16} />
                    Add business hours
                  </button>
                </form>
                <div className="business-hours-list">
                  {state.businessHours.length === 0 ? (
                    <p className="setup-module-hint">
                      No business hours yet. Add a calendar to define when SLA timers run.
                    </p>
                  ) : (
                    state.businessHours.map((calendar) => {
                      const draft = businessHoursDraftFor(calendar)
                      const dirty = Boolean(businessHoursDrafts[calendar.id])
                      return (
                        <article
                          className={`business-hours-card ${calendar.active ? 'active' : 'inactive'}`}
                          key={calendar.id}
                        >
                          <div className="business-hours-card-head">
                            <div>
                              <strong>{calendar.name}</strong>
                              <span>{calendar.timezone}</span>
                            </div>
                            <button
                              type="button"
                              className={calendar.active ? 'secondary-action' : 'primary-action'}
                              disabled={!canManageUsers}
                              onClick={() => void toggleBusinessHoursActive(calendar)}
                            >
                              {calendar.active ? 'Pause' : 'Activate'}
                            </button>
                          </div>
                          <div className="business-hours-grid">
                            {draft.map((day, index) => (
                              <div className={`business-hours-day ${day.enabled ? '' : 'off'}`} key={day.day}>
                                <label className="business-hours-day-toggle">
                                  <input
                                    type="checkbox"
                                    checked={day.enabled}
                                    disabled={!canManageUsers}
                                    onChange={(event) =>
                                      setBusinessHoursDayField(calendar, index, { enabled: event.target.checked })
                                    }
                                  />
                                  <span>{day.day}</span>
                                </label>
                                <input
                                  type="time"
                                  value={day.open}
                                  disabled={!canManageUsers || !day.enabled}
                                  onChange={(event) =>
                                    setBusinessHoursDayField(calendar, index, { open: event.target.value })
                                  }
                                  aria-label={`${day.day} open time`}
                                />
                                <span className="business-hours-dash">–</span>
                                <input
                                  type="time"
                                  value={day.close}
                                  disabled={!canManageUsers || !day.enabled}
                                  onChange={(event) =>
                                    setBusinessHoursDayField(calendar, index, { close: event.target.value })
                                  }
                                  aria-label={`${day.day} close time`}
                                />
                              </div>
                            ))}
                          </div>
                          {dirty ? (
                            <div className="business-hours-actions">
                              <button
                                type="button"
                                className="primary-action"
                                disabled={!canManageUsers}
                                onClick={() => void saveBusinessHoursSchedule(calendar)}
                              >
                                Save schedule
                              </button>
                              <button
                                type="button"
                                className="secondary-action"
                                onClick={() =>
                                  setBusinessHoursDrafts((drafts) => {
                                    const next = { ...drafts }
                                    delete next[calendar.id]
                                    return next
                                  })
                                }
                              >
                                Discard
                              </button>
                            </div>
                          ) : null}
                        </article>
                      )
                    })
                  )}
                </div>
              </section>
            ) : null}

            {peopleView === 'security' ? (
              <section className="people-section people-security-grid" aria-label="Security and identity">
                <form className="user-create-form password-change-form security-card" onSubmit={handleChangePassword}>
                  <div className="security-card-heading">
                    <div>
                      <h3>Password</h3>
                      <span>Current account</span>
                    </div>
                    <Lock size={17} />
                  </div>
                  <label>
                    <span>My current password</span>
                    <input
                      required
                      type="password"
                      value={passwordChange.currentPassword}
                      onChange={(event) =>
                        setPasswordChange((current) => ({
                          ...current,
                          currentPassword: event.target.value,
                        }))
                      }
                      placeholder="Current password"
                    />
                  </label>
                  <label>
                    <span>My new password</span>
                    <input
                      required
                      minLength={8}
                      type="password"
                      value={passwordChange.newPassword}
                      onChange={(event) =>
                        setPasswordChange((current) => ({
                          ...current,
                          newPassword: event.target.value,
                        }))
                      }
                      placeholder="Minimum 8 characters"
                    />
                  </label>
                  <button
                    className="secondary-action"
                    type="submit"
                    disabled={userActionBusy || passwordChange.currentPassword.length < 1 || passwordChange.newPassword.length < 8}
                  >
                    Update my password
                  </button>
                </form>
                <section className="user-create-form mfa-settings security-card">
                  <div className="security-card-heading">
                    <div>
                      <h3>Multi-factor authentication</h3>
                      <span>
                        {session.user.mfa_enabled
                          ? `Verified ${session.user.mfa_last_verified_at ? formatTime(session.user.mfa_last_verified_at) : 'recently'}`
                          : 'Not enabled'}
                      </span>
                    </div>
                    <em className={`chip status-${session.user.mfa_enabled ? 'healthy' : 'paused'}`}>
                      {session.user.mfa_enabled ? 'Enabled' : 'Optional'}
                    </em>
                  </div>
                  <button className="secondary-action" type="button" onClick={handleStartMfaEnrollment}>
                    <ShieldCheck size={16} />
                    {session.user.mfa_enabled ? 'Rotate MFA setup' : 'Start MFA setup'}
                  </button>
                  {mfaEnrollment ? (
                    <form className="mfa-enrollment" onSubmit={handleConfirmMfa}>
                      <label>
                        <span>Setup secret</span>
                        <input readOnly value={mfaEnrollment.secret} />
                      </label>
                      <label>
                        <span>Setup URI</span>
                        <input readOnly value={mfaEnrollment.otpauth_uri} />
                      </label>
                      <label>
                        <span>Confirmation code</span>
                        <input
                          required
                          inputMode="numeric"
                          minLength={6}
                          value={mfaConfirmCode}
                          onChange={(event) => setMfaConfirmCode(event.target.value)}
                          placeholder="6-digit code"
                        />
                      </label>
                      <button className="primary-action" type="submit" disabled={mfaConfirmCode.trim().length < 6}>
                        <Check size={16} />
                        Confirm MFA
                      </button>
                    </form>
                  ) : null}
                  {session.user.mfa_enabled ? (
                    <form className="mfa-enrollment" onSubmit={handleDisableMfa}>
                      <label>
                        <span>Current password</span>
                        <input
                          required
                          type="password"
                          value={mfaDisable.currentPassword}
                          onChange={(event) =>
                            setMfaDisable((current) => ({
                              ...current,
                              currentPassword: event.target.value,
                            }))
                          }
                          placeholder="Current password"
                        />
                      </label>
                      <label>
                        <span>MFA code</span>
                        <input
                          required
                          inputMode="numeric"
                          minLength={6}
                          value={mfaDisable.code}
                          onChange={(event) =>
                            setMfaDisable((current) => ({
                              ...current,
                              code: event.target.value,
                            }))
                          }
                          placeholder="6-digit code"
                        />
                      </label>
                      <button className="secondary-action" type="submit" disabled={mfaDisable.currentPassword.length < 1 || mfaDisable.code.trim().length < 6}>
                        Disable MFA
                      </button>
                    </form>
                  ) : null}
                </section>
                <section className="security-card">
                  <div className="security-card-heading">
                    <div>
                      <h3>Independent API status</h3>
                      <span>{backendSync.lastSyncAt ? `Last sync: ${formatTime(backendSync.lastSyncAt)}` : 'Not synced yet'}</span>
                    </div>
                    <RefreshCw size={17} />
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
                </section>
                <section className="security-card">
                  <div className="security-card-heading">
                    <div>
                      <h3>Enterprise SSO</h3>
                      <span>{oidcProviderConfig?.login_available ? 'Available' : 'Pending provider setup'}</span>
                    </div>
                    <ShieldCheck size={17} />
                  </div>
                  {ssoProviderSettings ? (
                    <form className="sso-settings-form" onSubmit={handleSsoSettingsSave}>
                      <label className="toggle-row compact-toggle">
                        <input
                          type="checkbox"
                          checked={ssoSettingsDraft.enabled}
                          onChange={(event) =>
                            setSsoSettingsDraft((current) => ({ ...current, enabled: event.target.checked }))
                          }
                          disabled={ssoSettingsBusy}
                        />
                        <span>Enable single sign-on login</span>
                      </label>
                      <div className="sso-settings-grid">
                        <label>
                          <span>Provider name</span>
                          <input
                            value={ssoSettingsDraft.providerName}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({ ...current, providerName: event.target.value }))
                            }
                            placeholder="Wakanow SSO"
                            disabled={ssoSettingsBusy}
                          />
                        </label>
                        <label>
                          <span>Issuer URL</span>
                          <input
                            value={ssoSettingsDraft.issuerUrl}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({ ...current, issuerUrl: event.target.value }))
                            }
                            placeholder="https://id.example.com"
                            disabled={ssoSettingsBusy}
                          />
                        </label>
                        <label>
                          <span>Authorization URL</span>
                          <input
                            value={ssoSettingsDraft.authorizationUrl}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({ ...current, authorizationUrl: event.target.value }))
                            }
                            placeholder="https://id.example.com/authorize"
                            disabled={ssoSettingsBusy}
                          />
                        </label>
                        <label>
                          <span>Token URL</span>
                          <input
                            value={ssoSettingsDraft.tokenUrl}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({ ...current, tokenUrl: event.target.value }))
                            }
                            placeholder="https://id.example.com/token"
                            disabled={ssoSettingsBusy}
                          />
                        </label>
                        <label>
                          <span>Userinfo URL</span>
                          <input
                            value={ssoSettingsDraft.userinfoUrl}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({ ...current, userinfoUrl: event.target.value }))
                            }
                            placeholder="https://id.example.com/userinfo"
                            disabled={ssoSettingsBusy}
                          />
                        </label>
                        <label>
                          <span>Redirect URL</span>
                          <input
                            value={ssoSettingsDraft.redirectUrl}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({ ...current, redirectUrl: event.target.value }))
                            }
                            placeholder="https://app.example.com/?auth=oidc"
                            disabled={ssoSettingsBusy}
                          />
                        </label>
                        <label>
                          <span>Client ID</span>
                          <input
                            value={ssoSettingsDraft.clientId}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({ ...current, clientId: event.target.value }))
                            }
                            placeholder="omni-web"
                            disabled={ssoSettingsBusy}
                          />
                        </label>
                        <label>
                          <span>Client secret</span>
                          <input
                            type="password"
                            value={ssoSettingsDraft.clientSecret}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({ ...current, clientSecret: event.target.value }))
                            }
                            placeholder={
                              ssoProviderSettings.client_secret_configured ? 'Saved secret' : 'Client secret'
                            }
                            disabled={ssoSettingsBusy || ssoSettingsDraft.clearClientSecret}
                            autoComplete="new-password"
                          />
                        </label>
                        <label>
                          <span>Default role</span>
                          <select
                            value={ssoSettingsDraft.defaultRole}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({
                                ...current,
                                defaultRole: event.target.value as BackendSsoProviderSettings['default_role'],
                              }))
                            }
                            disabled={ssoSettingsBusy}
                          >
                            {(['agent', 'supervisor', 'admin', 'viewer', 'owner'] as const).map((role) => (
                              <option key={role} value={role}>
                                {titleCase(role)}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          <span>Default market</span>
                          <select
                            value={ssoSettingsDraft.defaultMarketId}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({ ...current, defaultMarketId: event.target.value }))
                            }
                            disabled={ssoSettingsBusy}
                          >
                            <option value="">Use login market</option>
                            {availableMarkets.map((market) => (
                              <option key={market.id} value={market.id}>
                                {market.name}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <label className="sso-settings-full">
                        <span>Allowed email domains (comma separated)</span>
                        <input
                          value={ssoSettingsDraft.allowedEmailDomains}
                          onChange={(event) =>
                            setSsoSettingsDraft((current) => ({ ...current, allowedEmailDomains: event.target.value }))
                          }
                          placeholder="wakanow.com, partner.com"
                          disabled={ssoSettingsBusy}
                        />
                      </label>
                      <div className="sso-settings-toggles">
                        <label className="toggle-row compact-toggle">
                          <input
                            type="checkbox"
                            checked={ssoSettingsDraft.autoProvisionEnabled}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({
                                ...current,
                                autoProvisionEnabled: event.target.checked,
                              }))
                            }
                            disabled={ssoSettingsBusy}
                          />
                          <span>Auto-provision new SSO users</span>
                        </label>
                        <label className="toggle-row compact-toggle">
                          <input
                            type="checkbox"
                            checked={ssoSettingsDraft.requireEmailVerified}
                            onChange={(event) =>
                              setSsoSettingsDraft((current) => ({
                                ...current,
                                requireEmailVerified: event.target.checked,
                              }))
                            }
                            disabled={ssoSettingsBusy}
                          />
                          <span>Require verified email</span>
                        </label>
                        {ssoProviderSettings.client_secret_configured ? (
                          <label className="toggle-row compact-toggle">
                            <input
                              type="checkbox"
                              checked={ssoSettingsDraft.clearClientSecret}
                              onChange={(event) =>
                                setSsoSettingsDraft((current) => ({
                                  ...current,
                                  clearClientSecret: event.target.checked,
                                  clientSecret: event.target.checked ? '' : current.clientSecret,
                                }))
                              }
                              disabled={ssoSettingsBusy}
                            />
                            <span>Clear stored secret</span>
                          </label>
                        ) : null}
                      </div>
                      {oidcProviderConfig?.missing_settings.length ? (
                        <div className="readiness-note-list">
                          {oidcProviderConfig.missing_settings.slice(0, 6).map((setting) => (
                            <span key={setting}>{setting}</span>
                          ))}
                        </div>
                      ) : null}
                      <button type="submit" className="primary-action" disabled={ssoSettingsBusy}>
                        <ShieldCheck size={16} />
                        Save SSO settings
                      </button>
                    </form>
                  ) : (
                    <p className="setup-module-hint">
                      Sign in as an administrator to manage Enterprise SSO credentials.
                    </p>
                  )}
                </section>
              </section>
            ) : null}
          </div>
          ) : null}
          {setupSection === 'governance' ? (
          <div data-setup-panel="alerts" className="automation-settings-panel operational-alert-panel" id="operational-alerts">
            <div className="panel-head compact">
              <div>
                <span>Operational alerts</span>
                <h2>API, worker, SLA, and connector incidents</h2>
              </div>
              <AlertTriangle size={18} />
            </div>
            <div className="operational-alert-summary-grid" aria-label="Operational alert summary">
              {[
                ['Critical', criticalAlerts.length],
                ['Open', activeOperationalAlerts.filter((alert) => alert.status === 'open').length],
                ['Acknowledged', acknowledgedAlerts.length],
                ['Total active', activeOperationalAlerts.length],
              ].map(([label, value]) => (
                <article key={label}>
                  <strong>{value}</strong>
                  <span>{label}</span>
                </article>
              ))}
            </div>
            <div className="alert-delivery-config" aria-label="External alert delivery configuration">
              <article>
                <Bell size={16} />
                <span>
                  <strong>External delivery</strong>
                  <small>
                    {alertDeliveryConfig?.webhook_configured
                      ? `Webhook enabled for ${titleCase(alertDeliveryConfig.min_severity)} and above.`
                      : 'Pending alert webhook in Production credentials.'}
                  </small>
                </span>
              </article>
              <article>
                <Send size={16} />
                <span>
                  <strong>Delivery attempts</strong>
                  <small>
                    {sentAlertDeliveries.length} sent · {activeAlertDeliveries.length} waiting or failed.
                  </small>
                </span>
              </article>
            </div>
            <div className="operational-alert-list" aria-label="Operational alerts needing operator action">
              {activeOperationalAlerts.slice(0, 8).map((alert) => (
                <article className={`operational-alert-card severity-${alert.severity}`} key={alert.id}>
                  <div className="operational-alert-head">
                    <span className={`alert-severity-dot severity-${alert.severity}`} aria-hidden="true" />
                    <div>
                      <strong>{alert.title}</strong>
                      <span>{alert.message}</span>
                    </div>
                    <em className={`chip status-${operationalAlertStatusTone(alert.status)}`}>
                      {titleCase(alert.status)}
                    </em>
                  </div>
                  <div className="operational-alert-meta">
                    <span>{titleCase(alert.source)}</span>
                    <span>{operationalAlertEntityLabel(alert)}</span>
                    <span>{alert.occurrence_count} occurrence(s)</span>
                    <span>Last seen {formatTime(alert.last_seen_at)}</span>
                  </div>
                  {alert.acknowledged_by ? (
                    <small className="operational-alert-owner">
                      Acknowledged by {alert.acknowledged_by}
                    </small>
                  ) : null}
                  <div className="operational-alert-actions">
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => void handleOperationalAlertUpdate(alert, 'acknowledged')}
                      disabled={!canManageAlerts || alert.status === 'acknowledged'}
                    >
                      <Check size={15} />
                      Acknowledge
                    </button>
                    <button
                      className="primary-action"
                      type="button"
                      onClick={() => void handleOperationalAlertUpdate(alert, 'resolved')}
                      disabled={!canManageAlerts}
                    >
                      <CheckCircle2 size={15} />
                      Resolve
                    </button>
                  </div>
                </article>
              ))}
              {activeOperationalAlerts.length === 0 ? (
                <article className="operational-alert-empty">
                  <CheckCircle2 size={16} />
                  <span>No active operational alerts.</span>
                </article>
              ) : null}
            </div>
            <div className="alert-delivery-list" aria-label="External alert delivery attempts">
              {alertDeliveries.slice(0, 5).map((delivery) => (
                <article key={delivery.id}>
                  <div>
                    <strong>{titleCase(delivery.destination_type)} delivery</strong>
                    <span>
                      {delivery.status === 'sent'
                        ? `Sent ${delivery.sent_at ? formatTime(delivery.sent_at) : 'successfully'}`
                        : delivery.last_error ?? 'Waiting for worker dispatch.'}
                    </span>
                    <small>
                      {delivery.attempts}/{delivery.max_attempts} attempt(s) · {delivery.destination_name}
                    </small>
                  </div>
                  <em className={`chip status-${delivery.status === 'sent' ? 'done' : delivery.status === 'failed' ? 'failing' : 'pending'}`}>
                    {titleCase(delivery.status)}
                  </em>
                </article>
              ))}
              {alertDeliveries.length === 0 ? (
                <article className="operational-alert-empty">
                  <Bell size={16} />
                  <span>No external alert deliveries recorded yet.</span>
                </article>
              ) : null}
            </div>
          </div>
          ) : null}
          {setupSection === 'connectors' ? (
          <>
          <div data-setup-panel="widget" className="automation-settings-panel widget-settings-panel" id="widget-settings">
            <div className="panel-head compact">
              <div>
                <span>Chat widget</span>
                <h2>Embeddable web chat configuration</h2>
              </div>
              <MessageCircle size={18} />
            </div>
            {widgetSettings ? (
              <form className="sso-settings-form" onSubmit={handleWidgetSave}>
                <label className="toggle-row compact-toggle">
                  <input
                    type="checkbox"
                    checked={widgetDraft.enabled}
                    onChange={(event) => setWidgetDraft((current) => ({ ...current, enabled: event.target.checked }))}
                    disabled={widgetBusy}
                  />
                  <span>Enable the web chat widget</span>
                </label>
                <div className="sso-settings-grid">
                  <label>
                    <span>Header title</span>
                    <input
                      value={widgetDraft.displayName}
                      onChange={(event) => setWidgetDraft((current) => ({ ...current, displayName: event.target.value }))}
                      placeholder="Chat with us"
                      disabled={widgetBusy}
                    />
                  </label>
                  <label>
                    <span>Launcher label</span>
                    <input
                      value={widgetDraft.launcherLabel}
                      onChange={(event) => setWidgetDraft((current) => ({ ...current, launcherLabel: event.target.value }))}
                      placeholder="Support"
                      disabled={widgetBusy}
                    />
                  </label>
                  <label>
                    <span>Primary color</span>
                    <input
                      type="color"
                      value={widgetDraft.primaryColor}
                      onChange={(event) => setWidgetDraft((current) => ({ ...current, primaryColor: event.target.value }))}
                      disabled={widgetBusy}
                    />
                  </label>
                  <label>
                    <span>Position</span>
                    <select
                      value={widgetDraft.position}
                      onChange={(event) => setWidgetDraft((current) => ({ ...current, position: event.target.value }))}
                      disabled={widgetBusy}
                    >
                      <option value="bottom-right">Bottom right</option>
                      <option value="bottom-left">Bottom left</option>
                    </select>
                  </label>
                  <label>
                    <span>Auto-open after (seconds, 0 = off)</span>
                    <input
                      type="number"
                      min="0"
                      max="600"
                      value={widgetDraft.autoOpenSeconds}
                      onChange={(event) =>
                        setWidgetDraft((current) => ({ ...current, autoOpenSeconds: Number(event.target.value || 0) }))
                      }
                      disabled={widgetBusy}
                    />
                  </label>
                </div>
                <label className="sso-settings-full">
                  <span>Welcome message</span>
                  <textarea
                    rows={2}
                    value={widgetDraft.welcomeMessage}
                    onChange={(event) => setWidgetDraft((current) => ({ ...current, welcomeMessage: event.target.value }))}
                    placeholder="Hi! How can we help you today?"
                    disabled={widgetBusy}
                  />
                </label>
                <label className="sso-settings-full">
                  <span>Offline message</span>
                  <textarea
                    rows={2}
                    value={widgetDraft.offlineMessage}
                    onChange={(event) => setWidgetDraft((current) => ({ ...current, offlineMessage: event.target.value }))}
                    placeholder="We're offline right now — leave a message and we'll reply by email."
                    disabled={widgetBusy}
                  />
                </label>
                <label className="toggle-row compact-toggle">
                  <input
                    type="checkbox"
                    checked={widgetDraft.collectEmail}
                    onChange={(event) => setWidgetDraft((current) => ({ ...current, collectEmail: event.target.checked }))}
                    disabled={widgetBusy}
                  />
                  <span>Ask visitors for their email before chatting</span>
                </label>
                <button type="submit" className="primary-action" disabled={widgetBusy}>
                  <MessageCircle size={16} />
                  Save widget settings
                </button>
              </form>
            ) : (
              <p className="setup-module-hint">Sign in as an administrator to configure the chat widget.</p>
            )}
          </div>
          <form data-setup-panel="credentials" className="automation-settings-panel credential-settings-panel" onSubmit={handleIntegrationCredentialSave}>
            <div className="panel-head compact">
              <div>
                <span>Production credentials</span>
                <h2>AI, alerts, SMS, voice, and social channels</h2>
              </div>
              <Lock size={18} />
            </div>
            <div className="email-settings-status" aria-label="Production credential readiness">
              <article>
                <span className={`channel-health-dot ${integrationCredentialSettings?.anthropic_api_key_configured ? 'healthy' : 'degraded'}`} />
                <strong>AI</strong>
                <small>{integrationCredentialSettings?.anthropic_api_key_configured ? 'Anthropic key saved' : 'Anthropic key pending'}</small>
              </article>
              <article>
                <span className={`channel-health-dot ${integrationCredentialSettings?.alert_webhook_url ? 'healthy' : 'degraded'}`} />
                <strong>Alerts</strong>
                <small>{integrationCredentialSettings?.alert_webhook_url ? titleCase(integrationCredentialSettings.alert_delivery_min_severity) : 'Webhook pending'}</small>
              </article>
              <article>
                <Lock size={15} />
                <strong>Channel secrets</strong>
                <small>{savedChannelSecretCount} saved</small>
              </article>
            </div>
            <div className="credential-settings-grid">
              <details className="credential-settings-section" open>
                <summary>
                  <span className="credential-section-title">
                    <Bot size={16} />
                    <span>
                      <strong>AI and alerts</strong>
                      <small>{aiAlertReadyCount}/2 ready</small>
                    </span>
                  </span>
                  <em className={`chip status-${aiAlertReadyCount === 2 ? 'done' : 'pending'}`}>
                    {aiAlertReadyCount === 2 ? 'Ready' : 'Needs setup'}
                  </em>
                  <ChevronDown size={16} />
                </summary>
                <div className="credential-section-body">
                <label>
                  <span>AI provider</span>
                  <select
                    value={integrationCredentialDraft.aiProvider}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, aiProvider: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  >
                    <option value="auto">Auto</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="rules">Rules only</option>
                  </select>
                </label>
                <label>
                  <span>Anthropic base URL</span>
                  <input
                    value={integrationCredentialDraft.anthropicApiBaseUrl}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, anthropicApiBaseUrl: event.target.value }))
                    }
                    placeholder="https://api.anthropic.com"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Anthropic model</span>
                  <input
                    value={integrationCredentialDraft.anthropicModel}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, anthropicModel: event.target.value }))
                    }
                    placeholder="claude-sonnet-4-6"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Anthropic API key</span>
                  <input
                    type="password"
                    value={integrationCredentialDraft.anthropicApiKey}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, anthropicApiKey: event.target.value }))
                    }
                    placeholder={integrationCredentialSettings?.anthropic_api_key_configured ? 'Saved key' : 'Anthropic API key'}
                    disabled={!canManageIntegrationCredentials || integrationCredentialDraft.clearAnthropicApiKey}
                    autoComplete="new-password"
                  />
                </label>
                <label>
                  <span>Alert webhook URL</span>
                  <input
                    value={integrationCredentialDraft.alertWebhookUrl}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, alertWebhookUrl: event.target.value }))
                    }
                    placeholder="https://alerts.example.com/omni"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Alert secret</span>
                  <input
                    type="password"
                    value={integrationCredentialDraft.alertWebhookSecret}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, alertWebhookSecret: event.target.value }))
                    }
                    placeholder={integrationCredentialSettings?.alert_webhook_secret_configured ? 'Saved secret' : 'Webhook secret'}
                    disabled={!canManageIntegrationCredentials || integrationCredentialDraft.clearAlertWebhookSecret}
                    autoComplete="new-password"
                  />
                </label>
                <label>
                  <span>Alert severity</span>
                  <select
                    value={integrationCredentialDraft.alertDeliveryMinSeverity}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({
                        ...current,
                        alertDeliveryMinSeverity: event.target.value as IntegrationCredentialDraft['alertDeliveryMinSeverity'],
                      }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  >
                    <option value="info">Info</option>
                    <option value="warning">Warning</option>
                    <option value="critical">Critical</option>
                  </select>
                </label>
                <div className="email-settings-options">
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={integrationCredentialDraft.clearAnthropicApiKey}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({
                          ...current,
                          clearAnthropicApiKey: event.target.checked,
                          anthropicApiKey: event.target.checked ? '' : current.anthropicApiKey,
                        }))
                      }
                      disabled={!canManageIntegrationCredentials || !integrationCredentialSettings?.anthropic_api_key_configured}
                    />
                    <span>Clear AI key</span>
                  </label>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={integrationCredentialDraft.clearAlertWebhookSecret}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({
                          ...current,
                          clearAlertWebhookSecret: event.target.checked,
                          alertWebhookSecret: event.target.checked ? '' : current.alertWebhookSecret,
                        }))
                      }
                      disabled={!canManageIntegrationCredentials || !integrationCredentialSettings?.alert_webhook_secret_configured}
                    />
                    <span>Clear alert secret</span>
                  </label>
                </div>
                </div>
              </details>
              <details className="credential-settings-section">
                <summary>
                  <span className="credential-section-title">
                    <Phone size={16} />
                    <span>
                      <strong>SMS and voice</strong>
                      <small>{smsVoiceReadyCount}/2 secrets saved</small>
                    </span>
                  </span>
                  <em className={`chip status-${smsVoiceReadyCount === 2 ? 'done' : 'pending'}`}>
                    {smsVoiceReadyCount === 2 ? 'Ready' : 'Needs setup'}
                  </em>
                  <ChevronDown size={16} />
                </summary>
                <div className="credential-section-body">
                <label>
                  <span>SMS endpoint</span>
                  <input
                    value={integrationCredentialDraft.smsHttpEndpoint}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, smsHttpEndpoint: event.target.value }))
                    }
                    placeholder="https://sms.provider.com/messages"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>SMS sender</span>
                  <input
                    value={integrationCredentialDraft.smsHttpFrom}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, smsHttpFrom: event.target.value }))
                    }
                    placeholder="Wakanow"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>SMS token</span>
                  <input
                    type="password"
                    value={integrationCredentialDraft.smsHttpAuthToken}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, smsHttpAuthToken: event.target.value }))
                    }
                    placeholder={integrationCredentialSettings?.sms_http_auth_token_configured ? 'Saved token' : 'SMS API token'}
                    disabled={!canManageIntegrationCredentials || integrationCredentialDraft.clearSmsHttpAuthToken}
                    autoComplete="new-password"
                  />
                </label>
                <label>
                  <span>SMS callback URL</span>
                  <input
                    value={integrationCredentialDraft.smsHttpDeliveryCallbackUrl}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, smsHttpDeliveryCallbackUrl: event.target.value }))
                    }
                    placeholder="https://omni.wakanow.com/api/v1/webhooks/sms/ng"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <div className="credential-inline-grid">
                  <label>
                    <span>SMS header</span>
                    <input
                      value={integrationCredentialDraft.smsHttpAuthHeader}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({ ...current, smsHttpAuthHeader: event.target.value }))
                      }
                      disabled={!canManageIntegrationCredentials}
                    />
                  </label>
                  <label>
                    <span>SMS scheme</span>
                    <input
                      value={integrationCredentialDraft.smsHttpAuthScheme}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({ ...current, smsHttpAuthScheme: event.target.value }))
                      }
                      disabled={!canManageIntegrationCredentials}
                    />
                  </label>
                </div>
                <label>
                  <span>Voice endpoint</span>
                  <input
                    value={integrationCredentialDraft.voiceHttpEndpoint}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, voiceHttpEndpoint: event.target.value }))
                    }
                    placeholder="https://voice.provider.com/calls"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Voice caller ID</span>
                  <input
                    value={integrationCredentialDraft.voiceHttpFrom}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, voiceHttpFrom: event.target.value }))
                    }
                    placeholder="+234..."
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Voice token</span>
                  <input
                    type="password"
                    value={integrationCredentialDraft.voiceHttpAuthToken}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, voiceHttpAuthToken: event.target.value }))
                    }
                    placeholder={integrationCredentialSettings?.voice_http_auth_token_configured ? 'Saved token' : 'Voice API token'}
                    disabled={!canManageIntegrationCredentials || integrationCredentialDraft.clearVoiceHttpAuthToken}
                    autoComplete="new-password"
                  />
                </label>
                <label>
                  <span>Voice callback URL</span>
                  <input
                    value={integrationCredentialDraft.voiceHttpStatusCallbackUrl}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, voiceHttpStatusCallbackUrl: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <div className="email-settings-options">
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={integrationCredentialDraft.clearSmsHttpAuthToken}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({
                          ...current,
                          clearSmsHttpAuthToken: event.target.checked,
                          smsHttpAuthToken: event.target.checked ? '' : current.smsHttpAuthToken,
                        }))
                      }
                      disabled={!canManageIntegrationCredentials || !integrationCredentialSettings?.sms_http_auth_token_configured}
                    />
                    <span>Clear SMS token</span>
                  </label>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={integrationCredentialDraft.clearVoiceHttpAuthToken}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({
                          ...current,
                          clearVoiceHttpAuthToken: event.target.checked,
                          voiceHttpAuthToken: event.target.checked ? '' : current.voiceHttpAuthToken,
                        }))
                      }
                      disabled={!canManageIntegrationCredentials || !integrationCredentialSettings?.voice_http_auth_token_configured}
                    />
                    <span>Clear voice token</span>
                  </label>
                </div>
                </div>
              </details>
              <details className="credential-settings-section">
                <summary>
                  <span className="credential-section-title">
                    <MessageCircle size={16} />
                    <span>
                      <strong>Meta channels</strong>
                      <small>{metaReadyCount}/3 tokens saved</small>
                    </span>
                  </span>
                  <em className={`chip status-${metaReadyCount === 3 ? 'done' : 'pending'}`}>
                    {metaReadyCount === 3 ? 'Ready' : 'Needs setup'}
                  </em>
                  <ChevronDown size={16} />
                </summary>
                <div className="credential-section-body">
                <label>
                  <span>WhatsApp base URL</span>
                  <input
                    value={integrationCredentialDraft.whatsappCloudApiBaseUrl}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, whatsappCloudApiBaseUrl: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>WhatsApp phone ID</span>
                  <input
                    value={integrationCredentialDraft.whatsappPhoneNumberId}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, whatsappPhoneNumberId: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>WhatsApp token</span>
                  <input
                    type="password"
                    value={integrationCredentialDraft.whatsappAccessToken}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, whatsappAccessToken: event.target.value }))
                    }
                    placeholder={integrationCredentialSettings?.whatsapp_access_token_configured ? 'Saved token' : 'WhatsApp access token'}
                    disabled={!canManageIntegrationCredentials || integrationCredentialDraft.clearWhatsappAccessToken}
                    autoComplete="new-password"
                  />
                </label>
                <label>
                  <span>Facebook base URL</span>
                  <input
                    value={integrationCredentialDraft.facebookGraphApiBaseUrl}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, facebookGraphApiBaseUrl: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Facebook page ID</span>
                  <input
                    value={integrationCredentialDraft.facebookPageId}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, facebookPageId: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Facebook page token</span>
                  <input
                    type="password"
                    value={integrationCredentialDraft.facebookPageAccessToken}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, facebookPageAccessToken: event.target.value }))
                    }
                    placeholder={integrationCredentialSettings?.facebook_page_access_token_configured ? 'Saved token' : 'Facebook page token'}
                    disabled={!canManageIntegrationCredentials || integrationCredentialDraft.clearFacebookPageAccessToken}
                    autoComplete="new-password"
                  />
                </label>
                <label>
                  <span>Facebook message type</span>
                  <select
                    value={integrationCredentialDraft.facebookMessagingType}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, facebookMessagingType: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  >
                    <option value="RESPONSE">RESPONSE</option>
                    <option value="UPDATE">UPDATE</option>
                    <option value="MESSAGE_TAG">MESSAGE_TAG</option>
                  </select>
                </label>
                <label>
                  <span>Instagram base URL</span>
                  <input
                    value={integrationCredentialDraft.instagramGraphApiBaseUrl}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, instagramGraphApiBaseUrl: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Instagram account ID</span>
                  <input
                    value={integrationCredentialDraft.instagramBusinessAccountId}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, instagramBusinessAccountId: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Instagram token</span>
                  <input
                    type="password"
                    value={integrationCredentialDraft.instagramAccessToken}
                    onChange={(event) =>
                      setIntegrationCredentialDraft((current) => ({ ...current, instagramAccessToken: event.target.value }))
                    }
                    placeholder={integrationCredentialSettings?.instagram_access_token_configured ? 'Saved token' : 'Instagram access token'}
                    disabled={!canManageIntegrationCredentials || integrationCredentialDraft.clearInstagramAccessToken}
                    autoComplete="new-password"
                  />
                </label>
                <div className="email-settings-options">
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={integrationCredentialDraft.whatsappPreviewUrls}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({ ...current, whatsappPreviewUrls: event.target.checked }))
                      }
                      disabled={!canManageIntegrationCredentials}
                    />
                    <span>Preview URLs</span>
                  </label>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={integrationCredentialDraft.clearWhatsappAccessToken}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({
                          ...current,
                          clearWhatsappAccessToken: event.target.checked,
                          whatsappAccessToken: event.target.checked ? '' : current.whatsappAccessToken,
                        }))
                      }
                      disabled={!canManageIntegrationCredentials || !integrationCredentialSettings?.whatsapp_access_token_configured}
                    />
                    <span>Clear WhatsApp</span>
                  </label>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={integrationCredentialDraft.clearFacebookPageAccessToken}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({
                          ...current,
                          clearFacebookPageAccessToken: event.target.checked,
                          facebookPageAccessToken: event.target.checked ? '' : current.facebookPageAccessToken,
                        }))
                      }
                      disabled={!canManageIntegrationCredentials || !integrationCredentialSettings?.facebook_page_access_token_configured}
                    />
                    <span>Clear Facebook</span>
                  </label>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={integrationCredentialDraft.clearInstagramAccessToken}
                      onChange={(event) =>
                        setIntegrationCredentialDraft((current) => ({
                          ...current,
                          clearInstagramAccessToken: event.target.checked,
                          instagramAccessToken: event.target.checked ? '' : current.instagramAccessToken,
                        }))
                      }
                      disabled={!canManageIntegrationCredentials || !integrationCredentialSettings?.instagram_access_token_configured}
                    />
                    <span>Clear Instagram</span>
                  </label>
                </div>
                </div>
              </details>
            </div>
            <div className="email-settings-actions">
              <span>
                {integrationCredentialSettings
                  ? `Last saved ${formatTime(integrationCredentialSettings.updated_at)}`
                  : 'Backend credentials will appear after sync.'}
              </span>
              <button
                className="primary-action"
                type="submit"
                disabled={!canManageIntegrationCredentials || integrationCredentialBusy || !backendSession}
              >
                <Check size={15} />
                Save credentials
              </button>
            </div>
          </form>
          <section data-setup-panel="production" className="automation-settings-panel production-readiness-panel">
            <div className="panel-head compact">
              <div>
                <span>Launch gate</span>
                <h2>Production readiness</h2>
              </div>
              <Gauge size={18} />
            </div>
            <div className="email-settings-status" aria-label="Production launch readiness">
              <article>
                <span className={`channel-health-dot ${productionReadinessChecklist?.overall_status === 'ready' ? 'healthy' : 'degraded'}`} />
                <strong>{productionReadinessChecklist ? titleCase(productionReadinessChecklist.overall_status) : 'Loading'}</strong>
                <small>{productionReadinessChecklist ? `Generated ${formatTime(productionReadinessChecklist.generated_at)}` : 'Waiting for sync'}</small>
              </article>
              <article>
                <AlertTriangle size={15} />
                <strong>{productionReadinessChecklist?.blocked_items ?? 0}</strong>
                <small>Blocked</small>
              </article>
              <article>
                <Clock size={15} />
                <strong>{productionReadinessChecklist?.action_items ?? 0}</strong>
                <small>Action required</small>
              </article>
              <article>
                <CheckCircle2 size={15} />
                <strong>{productionReadinessChecklist?.ready_items ?? 0}</strong>
                <small>Ready</small>
              </article>
            </div>
            <div className="production-readiness-list">
              {(productionReadinessChecklist?.items ?? [])
                .filter((item) => item.status !== 'ready')
                .slice(0, 8)
                .map((item) => (
                  <article className="production-readiness-card" key={item.id}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>{item.category}</span>
                    </div>
                    <em className={`chip status-${productionRequestTone(item.status)}`}>
                      {titleCase(item.status)}
                    </em>
                    <small>{item.summary}</small>
                    <small>{item.next_action || item.evidence[0]}</small>
                  </article>
                ))}
              {productionReadinessChecklist && productionReadinessChecklist.items.every((item) => item.status === 'ready') ? (
                <article className="production-readiness-card is-ready">
                  <CheckCircle2 size={16} />
                  <span>All production readiness checks are clear.</span>
                </article>
              ) : null}
              {!productionReadinessChecklist && !productionReadinessBusy ? (
                <article className="production-readiness-card">
                  <span>Production readiness checklist will appear after refresh.</span>
                </article>
              ) : null}
            </div>
            <div className="email-settings-actions">
              <span>
                {productionReadinessChecklist
                  ? `${productionReadinessChecklist.total_items} check(s) · ${productionReadinessChecklist.blocked_items} blocker(s)`
                  : 'Production launch gate is not loaded.'}
              </span>
              <button
                className="secondary-action"
                type="button"
                onClick={() => void handleProductionReadinessRefresh()}
                disabled={!backendSession || productionReadinessBusy}
              >
                <RefreshCw size={15} />
                Refresh
              </button>
            </div>
          </section>
          <section data-setup-panel="production" className="automation-settings-panel account-request-panel">
            <div className="panel-head compact">
              <div>
                <span>Account requests</span>
                <h2>Provider activation pack</h2>
              </div>
              <ClipboardList size={18} />
            </div>
            <div className="email-settings-status" aria-label="Production account request readiness">
              <article>
                <span className={`channel-health-dot ${productionAccountPack?.missing_items ? 'degraded' : 'healthy'}`} />
                <strong>{productionAccountPack?.missing_items ?? 0}</strong>
                <small>Action item(s)</small>
              </article>
              <article>
                <CheckCircle2 size={15} />
                <strong>{productionAccountPack?.ready_items ?? 0}</strong>
                <small>Ready</small>
              </article>
              <article>
                <Mail size={15} />
                <strong>{productionAccountPack?.recipient_email ?? 'gbolahans@wakanow.com'}</strong>
                <small>{productionAccountPack ? `Generated ${formatTime(productionAccountPack.generated_at)}` : 'Waiting for sync'}</small>
              </article>
              <article>
                <Send size={15} />
                <strong>{productionAccountDelivery ? titleCase(productionAccountDelivery.outbound_message.status) : 'Not queued'}</strong>
                <small>
                  {productionAccountDelivery
                    ? `${productionAccountDelivery.ticket_public_id} · ${formatTime(productionAccountDelivery.queued_at)}`
                    : 'Admin action'}
                </small>
              </article>
            </div>
            <div className="account-request-list">
              {productionAccountActionItems.slice(0, 6).map((item) => (
                <article className="account-request-card" key={item.id}>
                  <div>
                    <strong>{item.area}</strong>
                    <span>{item.provider}</span>
                  </div>
                  <em className={`chip status-${productionRequestTone(item.status)}`}>
                    {titleCase(item.status)}
                  </em>
                  <small>{item.missing_settings.slice(0, 3).join(' · ') || item.notes}</small>
                  {item.callback_urls[0] ? <small>{item.callback_urls[0]}</small> : null}
                </article>
              ))}
              {productionAccountPack && productionAccountActionItems.length === 0 ? (
                <article className="account-request-card is-ready">
                  <CheckCircle2 size={16} />
                  <span>All provider account requests are ready for this market.</span>
                </article>
              ) : null}
              {!productionAccountPack && !productionAccountBusy ? (
                <article className="account-request-card">
                  <span>Backend account request pack will appear after refresh.</span>
                </article>
              ) : null}
            </div>
            <textarea
              className="request-body-preview"
              value={productionAccountPack?.body ?? ''}
              readOnly
              aria-label="Account request email body"
            />
            <div className="email-settings-actions">
              <span>
                {productionAccountPack
                  ? `${productionAccountPack.total_items} provider item(s) · ${productionAccountPack.subject}`
                  : 'Production account request pack is not loaded.'}
              </span>
              <button
                className="secondary-action"
                type="button"
                onClick={() => void handleProductionAccountRefresh()}
                disabled={!backendSession || productionAccountBusy}
              >
                <RefreshCw size={15} />
                Refresh
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() => void handleProductionAccountCopy()}
                disabled={!productionAccountPack}
              >
                <ClipboardList size={15} />
                Copy
              </button>
              <button
                className="primary-action"
                type="button"
                onClick={() => void handleProductionAccountSend()}
                disabled={!backendSession || !canManageIntegrationCredentials || productionAccountSendBusy}
              >
                <Send size={15} />
                Queue email
              </button>
              <a
                className={`secondary-action ${productionAccountPack ? '' : 'disabled'}`}
                href={productionAccountPack?.mailto_url ?? '#'}
                onClick={(event) => {
                  if (!productionAccountPack) event.preventDefault()
                }}
              >
                <Mail size={15} />
                Email draft
              </a>
            </div>
          </section>
          <section data-setup-panel="production" className="automation-settings-panel account-reference-panel">
            <div className="panel-head compact">
              <div>
                <span>Account references</span>
                <h2>Non-secret provider records</h2>
              </div>
              <DatabaseZap size={18} />
            </div>
            <div className="email-settings-status" aria-label="Production account reference summary">
              <article>
                <DatabaseZap size={15} />
                <strong>{productionAccountReferences.length}</strong>
                <small>Saved reference(s)</small>
              </article>
              <article>
                <CheckCircle2 size={15} />
                <strong>
                  {productionAccountReferences.filter((reference) => reference.status === 'connected').length}
                </strong>
                <small>Connected</small>
              </article>
              <article>
                <ClipboardList size={15} />
                <strong>{productionAccountReferenceDocs ? 'Ready' : 'Pending'}</strong>
                <small>API_DOCS snippet</small>
              </article>
            </div>
            <div className="account-reference-list">
              {productionAccountReferences.slice(0, 6).map((reference) => (
                <article className="account-reference-card" key={reference.id}>
                  <div>
                    <strong>{reference.account_name}</strong>
                    <span>{reference.provider} · {reference.area}</span>
                  </div>
                  <em className={`chip status-${productionRequestTone(reference.status === 'connected' ? 'ready' : reference.status === 'blocked' ? 'missing' : 'action_required')}`}>
                    {titleCase(reference.status)}
                  </em>
                  <small>{reference.account_identifier || reference.credential_reference || 'Identifier pending'}</small>
                  <small>{reference.docs_reference || 'API_DOCS reference pending'}</small>
                  <div className="account-reference-actions">
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => void handleProductionAccountReferenceStatus(reference, 'connected')}
                      disabled={!canManageIntegrationCredentials || productionAccountReferenceBusy || reference.status === 'connected'}
                    >
                      <CheckCircle2 size={14} />
                      Connected
                    </button>
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => void handleProductionAccountReferenceStatus(reference, 'blocked')}
                      disabled={!canManageIntegrationCredentials || productionAccountReferenceBusy || reference.status === 'blocked'}
                    >
                      <AlertTriangle size={14} />
                      Blocked
                    </button>
                  </div>
                </article>
              ))}
              {productionAccountReferences.length === 0 ? (
                <article className="account-reference-card">
                  <span>No provider account references saved yet.</span>
                </article>
              ) : null}
            </div>
            <form className="account-reference-form" onSubmit={handleProductionAccountReferenceSave}>
              <div className="account-reference-grid">
                <label>
                  <span>Provider</span>
                  <input
                    value={productionAccountReferenceDraft.provider}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({ ...current, provider: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Area</span>
                  <input
                    value={productionAccountReferenceDraft.area}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({ ...current, area: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Account name</span>
                  <input
                    value={productionAccountReferenceDraft.accountName}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({ ...current, accountName: event.target.value }))
                    }
                    placeholder="Wakanow NG WhatsApp Business"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Account identifier</span>
                  <input
                    value={productionAccountReferenceDraft.accountIdentifier}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({ ...current, accountIdentifier: event.target.value }))
                    }
                    placeholder="Provider account ID or phone ID"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Status</span>
                  <select
                    value={productionAccountReferenceDraft.status}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({
                        ...current,
                        status: event.target.value as BackendProductionAccountReferenceStatus,
                      }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  >
                    {productionReferenceStatusOptions.map((statusOption) => (
                      <option key={statusOption} value={statusOption}>{titleCase(statusOption)}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Owner email</span>
                  <input
                    type="email"
                    value={productionAccountReferenceDraft.ownerEmail}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({ ...current, ownerEmail: event.target.value }))
                    }
                    placeholder="owner@wakanow.com"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Credential reference</span>
                  <input
                    value={productionAccountReferenceDraft.credentialReference}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({ ...current, credentialReference: event.target.value }))
                    }
                    placeholder="vault://omni/ng/provider/token"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>API_DOCS reference</span>
                  <input
                    value={productionAccountReferenceDraft.docsReference}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({ ...current, docsReference: event.target.value }))
                    }
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Callback URLs</span>
                  <textarea
                    value={productionAccountReferenceDraft.callbackUrls}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({ ...current, callbackUrls: event.target.value }))
                    }
                    placeholder="One URL per line"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
                <label>
                  <span>Notes</span>
                  <textarea
                    value={productionAccountReferenceDraft.notes}
                    onChange={(event) =>
                      setProductionAccountReferenceDraft((current) => ({ ...current, notes: event.target.value }))
                    }
                    placeholder="Non-secret operational notes"
                    disabled={!canManageIntegrationCredentials}
                  />
                </label>
              </div>
              <textarea
                className="request-body-preview docs-snippet-preview"
                value={productionAccountReferenceDocs?.markdown ?? ''}
                readOnly
                aria-label="API_DOCS account reference snippet"
              />
              <div className="email-settings-actions">
                <span>Save non-secret references only. Tokens, passwords, and private keys stay out of this table.</span>
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() => void handleProductionAccountReferenceDocsCopy()}
                  disabled={!productionAccountReferenceDocs}
                >
                  <ClipboardList size={15} />
                  Copy snippet
                </button>
                <button
                  className="primary-action"
                  type="submit"
                  disabled={!canManageIntegrationCredentials || productionAccountReferenceBusy || !backendSession}
                >
                  <Check size={15} />
                  Save reference
                </button>
              </div>
            </form>
          </section>
          <form data-setup-panel="email" className="automation-settings-panel email-settings-panel" onSubmit={handleEmailSettingsSave}>
            <div className="panel-head compact">
              <div>
                <span>Email setup</span>
                <h2>Mailbox intake and replies</h2>
              </div>
              <Mail size={18} />
            </div>
            <p className="setup-module-hint">
              This is the shared mailbox <b>transport</b> (IMAP intake + SMTP delivery) for this
              market. Per-team / per-function addresses are set on each team's <b>Team email</b> in
              People → Groups (e.g. billing-support@, fulfillment@). Inbound mail addressed to a
              team routes to that team's queue, and replies send from the team address.
            </p>
            <div className="email-settings-status" aria-label="Email setup readiness">
              <article>
                <span className={`channel-health-dot ${emailInboundConfig?.live_intake ? 'healthy' : 'degraded'}`} />
                <strong>Inbound</strong>
                <small>{emailInboundConfig?.live_intake ? 'IMAP live' : emailInboundConfig?.missing_settings.slice(0, 2).join(' · ') || 'Pending setup'}</small>
              </article>
              <article>
                <span className={`channel-health-dot ${emailOutboundConfig?.live_delivery ? 'healthy' : 'degraded'}`} />
                <strong>Outbound</strong>
                <small>{emailOutboundConfig?.live_delivery ? 'SMTP live' : emailOutboundConfig?.missing_settings.slice(0, 2).join(' · ') || 'Pending setup'}</small>
              </article>
              <article>
                <Lock size={15} />
                <strong>Secrets</strong>
                <small>
                  {emailProviderSettings?.inbound_password_configured || emailProviderSettings?.outbound_password_configured
                    ? 'Stored write-only'
                    : 'Not saved yet'}
                </small>
              </article>
            </div>
            <div className="email-settings-grid">
              <section>
                <div className="email-settings-heading">
                  <Inbox size={16} />
                  <strong>IMAP intake</strong>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={emailSettingsDraft.inboundEnabled}
                      onChange={(event) =>
                        setEmailSettingsDraft((current) => ({ ...current, inboundEnabled: event.target.checked }))
                      }
                      disabled={!canManageEmailSettings}
                    />
                    <span>Enabled</span>
                  </label>
                </div>
                <label>
                  <span>Host</span>
                  <input
                    value={emailSettingsDraft.inboundHost}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, inboundHost: event.target.value }))
                    }
                    placeholder="imap.provider.com"
                    disabled={!canManageEmailSettings}
                  />
                </label>
                <label>
                  <span>Port</span>
                  <input
                    type="number"
                    min="1"
                    max="65535"
                    value={emailSettingsDraft.inboundPort}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, inboundPort: Number(event.target.value || 993) }))
                    }
                    disabled={!canManageEmailSettings}
                  />
                </label>
                <label>
                  <span>Username</span>
                  <input
                    value={emailSettingsDraft.inboundUsername}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, inboundUsername: event.target.value }))
                    }
                    placeholder="jimb@wakanow.com"
                    disabled={!canManageEmailSettings}
                  />
                </label>
                <label>
                  <span>Mailbox</span>
                  <input
                    value={emailSettingsDraft.inboundMailbox}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, inboundMailbox: event.target.value }))
                    }
                    placeholder="INBOX"
                    disabled={!canManageEmailSettings}
                  />
                </label>
                <label>
                  <span>Password</span>
                  <input
                    type="password"
                    value={emailSettingsDraft.inboundPassword}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, inboundPassword: event.target.value }))
                    }
                    placeholder={emailProviderSettings?.inbound_password_configured ? 'Saved password' : 'Mailbox password'}
                    disabled={!canManageEmailSettings || emailSettingsDraft.clearInboundPassword}
                    autoComplete="new-password"
                  />
                </label>
                <div className="email-settings-options">
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={emailSettingsDraft.inboundUseSsl}
                      onChange={(event) =>
                        setEmailSettingsDraft((current) => ({ ...current, inboundUseSsl: event.target.checked }))
                      }
                      disabled={!canManageEmailSettings}
                    />
                    <span>SSL</span>
                  </label>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={emailSettingsDraft.inboundMarkSeen}
                      onChange={(event) =>
                        setEmailSettingsDraft((current) => ({ ...current, inboundMarkSeen: event.target.checked }))
                      }
                      disabled={!canManageEmailSettings}
                    />
                    <span>Mark seen</span>
                  </label>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={emailSettingsDraft.clearInboundPassword}
                      onChange={(event) =>
                        setEmailSettingsDraft((current) => ({
                          ...current,
                          clearInboundPassword: event.target.checked,
                          inboundPassword: event.target.checked ? '' : current.inboundPassword,
                        }))
                      }
                      disabled={!canManageEmailSettings || !emailProviderSettings?.inbound_password_configured}
                    />
                    <span>Clear password</span>
                  </label>
                </div>
              </section>
              <section>
                <div className="email-settings-heading">
                  <Send size={16} />
                  <strong>SMTP replies</strong>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={emailSettingsDraft.outboundEnabled}
                      onChange={(event) =>
                        setEmailSettingsDraft((current) => ({ ...current, outboundEnabled: event.target.checked }))
                      }
                      disabled={!canManageEmailSettings}
                    />
                    <span>Enabled</span>
                  </label>
                </div>
                <label>
                  <span>Host</span>
                  <input
                    value={emailSettingsDraft.outboundHost}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, outboundHost: event.target.value }))
                    }
                    placeholder="smtp.provider.com"
                    disabled={!canManageEmailSettings}
                  />
                </label>
                <label>
                  <span>Port</span>
                  <input
                    type="number"
                    min="1"
                    max="65535"
                    value={emailSettingsDraft.outboundPort}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, outboundPort: Number(event.target.value || 587) }))
                    }
                    disabled={!canManageEmailSettings}
                  />
                </label>
                <label>
                  <span>Username</span>
                  <input
                    value={emailSettingsDraft.outboundUsername}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, outboundUsername: event.target.value }))
                    }
                    placeholder="jimb@wakanow.com"
                    disabled={!canManageEmailSettings}
                  />
                </label>
                <label>
                  <span>From address</span>
                  <input
                    value={emailSettingsDraft.outboundFromEmail}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, outboundFromEmail: event.target.value }))
                    }
                    placeholder="jimb@wakanow.com"
                    disabled={!canManageEmailSettings}
                  />
                </label>
                <label>
                  <span>Password</span>
                  <input
                    type="password"
                    value={emailSettingsDraft.outboundPassword}
                    onChange={(event) =>
                      setEmailSettingsDraft((current) => ({ ...current, outboundPassword: event.target.value }))
                    }
                    placeholder={emailProviderSettings?.outbound_password_configured ? 'Saved password' : 'SMTP password'}
                    disabled={!canManageEmailSettings || emailSettingsDraft.clearOutboundPassword}
                    autoComplete="new-password"
                  />
                </label>
                <div className="email-settings-options">
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={emailSettingsDraft.outboundUseStarttls}
                      onChange={(event) =>
                        setEmailSettingsDraft((current) => ({
                          ...current,
                          outboundUseStarttls: event.target.checked,
                          outboundUseSsl: event.target.checked ? false : current.outboundUseSsl,
                        }))
                      }
                      disabled={!canManageEmailSettings}
                    />
                    <span>STARTTLS</span>
                  </label>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={emailSettingsDraft.outboundUseSsl}
                      onChange={(event) =>
                        setEmailSettingsDraft((current) => ({
                          ...current,
                          outboundUseSsl: event.target.checked,
                          outboundUseStarttls: event.target.checked ? false : current.outboundUseStarttls,
                        }))
                      }
                      disabled={!canManageEmailSettings}
                    />
                    <span>SSL</span>
                  </label>
                  <label className="toggle-row compact-toggle">
                    <input
                      type="checkbox"
                      checked={emailSettingsDraft.clearOutboundPassword}
                      onChange={(event) =>
                        setEmailSettingsDraft((current) => ({
                          ...current,
                          clearOutboundPassword: event.target.checked,
                          outboundPassword: event.target.checked ? '' : current.outboundPassword,
                        }))
                      }
                      disabled={!canManageEmailSettings || !emailProviderSettings?.outbound_password_configured}
                    />
                    <span>Clear password</span>
                  </label>
                </div>
              </section>
            </div>
            <div className="email-settings-actions">
              <span>
                {emailProviderSettings
                  ? `Last saved ${formatTime(emailProviderSettings.updated_at)}`
                  : 'Backend email settings will appear after sync.'}
              </span>
              <button
                className="primary-action"
                type="submit"
                disabled={!canManageEmailSettings || emailSettingsBusy || !backendSession}
              >
                <Check size={15} />
                Save email setup
              </button>
            </div>
          </form>
          <div data-setup-panel="email" className="automation-settings-panel team-inbox-overview">
            <div className="panel-head compact">
              <div>
                <span>Team inboxes</span>
                <h2>Where each team&rsquo;s mail lands</h2>
              </div>
              <Inbox size={18} />
            </div>
            <p className="setup-module-hint">
              Mail addressed to a team routes to that team&rsquo;s queue, and replies send from the
              team address. Set or change an address on each team in People &rarr; Groups.
            </p>
            <div className="team-inbox-table" role="table" aria-label="Team inboxes">
              <div className="team-inbox-row team-inbox-head" role="row">
                <span role="columnheader">Team</span>
                <span role="columnheader">Inbox address</span>
                <span role="columnheader">Channels</span>
                <span role="columnheader">Open</span>
              </div>
              {state.supportGroups.map((group) => (
                <div className={`team-inbox-row${group.teamEmail ? '' : ' unset'}`} role="row" key={group.id}>
                  <span role="cell"><strong>{group.name}</strong></span>
                  <span role="cell" className="team-inbox-addr">
                    {group.teamEmail ? (
                      <>
                        <Mail size={13} />
                        {group.teamEmail}
                      </>
                    ) : (
                      <em>No inbox set</em>
                    )}
                  </span>
                  <span role="cell" className="team-inbox-channels">
                    {group.channels.length ? (
                      group.channels.slice(0, 4).map((channel) => <span key={channel}>{titleCase(channel)}</span>)
                    ) : (
                      <em>&mdash;</em>
                    )}
                  </span>
                  <span role="cell"><b>{group.openTicketCount}</b></span>
                </div>
              ))}
              {state.supportGroups.length === 0 ? (
                <div className="team-inbox-row" role="row">
                  <span role="cell">No teams yet — add one in People &rarr; Groups.</span>
                </div>
              ) : null}
            </div>
            <div className="email-settings-actions">
              <span>
                {state.supportGroups.filter((group) => group.teamEmail).length} of {state.supportGroups.length} teams
                have an inbox address.
              </span>
              <button className="secondary-action" type="button" onClick={() => openSetupModule('Groups')}>
                <Users size={15} />
                Manage in People &rarr; Groups
              </button>
            </div>
          </div>
          <div data-setup-panel="credentials" className="automation-settings-panel outbound-provider-panel">
            <div className="panel-head compact">
              <div>
                <span>Inbound adapters</span>
                <h2>Provider intake readiness</h2>
              </div>
              <Inbox size={18} />
            </div>
            <div className="outbound-provider-grid" aria-label="Inbound provider adapter readiness">
              {inboundProviderConfig.map((config) => (
                <article key={`${config.provider}-${config.adapter}`}>
                  <div className="outbound-provider-head">
                    <span className={`channel-health-dot ${config.live_intake ? 'healthy' : 'degraded'}`} />
                    <div>
                      <strong>{titleCase(config.provider)} inbound</strong>
                      <small>{config.notes}</small>
                    </div>
                    <em className={`chip status-${config.live_intake ? 'done' : 'pending'}`}>
                      {config.live_intake ? 'Live' : 'Pending'}
                    </em>
                  </div>
                  <div className="outbound-provider-meta">
                    <span>
                      <b>Adapter</b>
                      {titleCase(config.adapter)}
                    </span>
                    <span>
                      <b>Polling</b>
                      {config.polling_enabled ? 'On' : 'Off'}
                    </span>
                    <span>
                      <b>Missing</b>
                      {config.missing_settings.length || 'None'}
                    </span>
                  </div>
                  {config.missing_settings.length ? (
                    <div className="connector-needed">
                      <AlertTriangle size={15} />
                      <span>{config.missing_settings.slice(0, 2).join(' · ')}</span>
                    </div>
                  ) : null}
                </article>
              ))}
              {inboundProviderConfig.length === 0 ? (
                <article className="outbound-empty">
                  <AlertTriangle size={16} />
                  <span>Inbound adapter readiness is not available for this role.</span>
                </article>
              ) : null}
            </div>
          </div>
          <div data-setup-panel="credentials" className="automation-settings-panel outbound-provider-panel">
            <div className="panel-head compact">
              <div>
                <span>Outbound adapters</span>
                <h2>Provider send readiness</h2>
              </div>
              <Send size={18} />
            </div>
            <div className="outbound-provider-grid" aria-label="Outbound provider adapter readiness">
              {outboundProviderConfig.map((config) => (
                <article key={`${config.provider}-${config.adapter}`}>
                  <div className="outbound-provider-head">
                    <span className={`channel-health-dot ${config.live_delivery ? 'healthy' : 'degraded'}`} />
                    <div>
                      <strong>{titleCase(config.provider)} outbound</strong>
                      <small>{config.notes}</small>
                    </div>
                    <em className={`chip status-${config.live_delivery ? 'done' : 'pending'}`}>
                      {config.live_delivery ? 'Live' : 'Pending'}
                    </em>
                  </div>
                  <div className="outbound-provider-meta">
                    <span>
                      <b>Adapter</b>
                      {titleCase(config.adapter)}
                    </span>
                    <span>
                      <b>Fallback</b>
                      {config.fallback_adapter ? titleCase(config.fallback_adapter) : 'Off'}
                    </span>
                    <span>
                      <b>Missing</b>
                      {config.missing_settings.length || 'None'}
                    </span>
                  </div>
                  {config.missing_settings.length ? (
                    <div className="connector-needed">
                      <AlertTriangle size={15} />
                      <span>{config.missing_settings.slice(0, 2).join(' · ')}</span>
                    </div>
                  ) : null}
                </article>
              ))}
              {outboundProviderConfig.length === 0 ? (
                <article className="outbound-empty">
                  <AlertTriangle size={16} />
                  <span>Outbound adapter readiness is not available for this role.</span>
                </article>
              ) : null}
            </div>
          </div>
          <div data-setup-panel="credentials" className="automation-settings-panel connector-control-center">
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
          <div data-setup-panel="credentials" className="automation-settings-panel outbound-queue-panel" id="outbound-queue">
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
          </>
          ) : null}
          {setupSection === 'automation' ? (
          <>
          <div data-setup-panel="automations" className="automation-settings-panel">
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
                  AI keeps the Work Queue moving unless this switch is turned off by an admin.
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
	          <div data-setup-panel="sla" className="automation-settings-panel sla-policy-panel">
	            <div className="panel-head compact">
	              <div>
	                <span>SLA policies</span>
	                <h2>Promise targets</h2>
	              </div>
	              <button
	                className={addSlaPolicyOpen ? 'secondary-action' : 'primary-action'}
	                type="button"
	                onClick={() => setAddSlaPolicyOpen((value) => !value)}
	                disabled={!canManageSlaPolicies}
	                aria-expanded={addSlaPolicyOpen}
	              >
	                {addSlaPolicyOpen ? <X size={16} /> : <Plus size={16} />}
	                {addSlaPolicyOpen ? 'Close form' : 'Add policy'}
	              </button>
	            </div>
	            <div className="sla-summary-strip" aria-label="SLA policy summary">
	              <article>
	                <strong>{activeSlaPolicies.length}</strong>
	                <span>Active</span>
	              </article>
	              <article>
	                <strong>{state.slaPolicies.length - activeSlaPolicies.length}</strong>
	                <span>Paused</span>
	              </article>
	              <article>
	                <strong>{state.slaPolicies.filter((policy) => policy.priority === 'urgent').length}</strong>
	                <span>Urgent rules</span>
	              </article>
	            </div>
	            {addSlaPolicyOpen ? (
	              <form className="user-create-form sla-policy-form" onSubmit={handleCreateSlaPolicy}>
	                <label>
	                  <span>Policy name</span>
	                  <input
	                    required
	                    value={slaPolicyDraft.name}
	                    onChange={(event) =>
	                      setSlaPolicyDraft((current) => ({ ...current, name: event.target.value }))
	                    }
	                    placeholder="VIP API response"
	                    disabled={!canManageSlaPolicies || slaPolicyActionBusy}
	                  />
	                </label>
	                <label>
	                  <span>Priority</span>
	                  <select
	                    value={slaPolicyDraft.priority}
	                    onChange={(event) =>
	                      setSlaPolicyDraft((current) => ({
	                        ...current,
	                        priority: event.target.value as Priority,
	                      }))
	                    }
	                    disabled={!canManageSlaPolicies || slaPolicyActionBusy}
	                  >
		                    {priorityOptions
		                      .filter((option): option is Priority => option !== 'all')
		                      .map((priority) => (
		                        <option key={priority} value={priority}>
		                          {titleCase(priority)}
		                        </option>
		                      ))}
	                  </select>
	                </label>
	                <label>
	                  <span>First reply minutes</span>
	                  <input
	                    type="number"
	                    min={1}
	                    value={slaPolicyDraft.firstResponseMinutes}
	                    onChange={(event) =>
	                      setSlaPolicyDraft((current) => ({
	                        ...current,
	                        firstResponseMinutes: Number(event.target.value),
	                      }))
	                    }
	                    disabled={!canManageSlaPolicies || slaPolicyActionBusy}
	                  />
	                </label>
	                <label>
	                  <span>Resolution minutes</span>
	                  <input
	                    type="number"
	                    min={1}
	                    value={slaPolicyDraft.resolutionMinutes}
	                    onChange={(event) =>
	                      setSlaPolicyDraft((current) => ({
	                        ...current,
	                        resolutionMinutes: Number(event.target.value),
	                      }))
	                    }
	                    disabled={!canManageSlaPolicies || slaPolicyActionBusy}
	                  />
	                </label>
	                <label>
	                  <span>Business hours</span>
	                  <input
	                    value={slaPolicyDraft.businessHours}
	                    onChange={(event) =>
	                      setSlaPolicyDraft((current) => ({
	                        ...current,
	                        businessHours: event.target.value,
	                      }))
	                    }
	                    placeholder="24x7"
	                    disabled={!canManageSlaPolicies || slaPolicyActionBusy}
	                  />
	                </label>
	                <label>
	                  <span>Position</span>
	                  <input
	                    type="number"
	                    value={slaPolicyDraft.position}
		                    onChange={(event) =>
		                      setSlaPolicyDraft((current) => ({
		                        ...current,
		                        position: Number(event.target.value),
		                      }))
		                    }
	                    disabled={!canManageSlaPolicies || slaPolicyActionBusy}
	                  />
	                </label>
	                <div className="user-market-picker" aria-label="SLA channels">
	                  <span>Channels</span>
	                  <div>
	                    {state.channels.slice(0, 8).map((channel) => (
	                      <label key={channel.id}>
	                        <input
	                          type="checkbox"
	                          checked={slaPolicyDraft.channels.includes(channel.id)}
	                          onChange={() => toggleSlaPolicyDraftChannel(channel.id)}
	                          disabled={!canManageSlaPolicies || slaPolicyActionBusy}
	                        />
	                        {channel.shortLabel}
	                      </label>
	                    ))}
	                  </div>
	                </div>
	                <label className="setting-row compact-toggle">
	                  <span>
	                    <strong>Active</strong>
	                    <small>Use this policy for matching new tickets.</small>
	                  </span>
	                  <input
	                    type="checkbox"
	                    role="switch"
	                    checked={slaPolicyDraft.active}
	                    onChange={(event) =>
	                      setSlaPolicyDraft((current) => ({ ...current, active: event.target.checked }))
	                    }
	                    disabled={!canManageSlaPolicies || slaPolicyActionBusy}
	                  />
	                </label>
	                <div className="form-actions">
		                  <button
		                    className="secondary-action"
		                    type="button"
		                    onClick={() => setAddSlaPolicyOpen(false)}
		                  >
		                    Cancel
		                  </button>
		                  <button
		                    className="primary-action"
		                    type="submit"
		                    disabled={!canManageSlaPolicies || slaPolicyActionBusy}
		                  >
	                    <Plus size={16} />
	                    {slaPolicyActionBusy ? 'Saving...' : 'Add policy'}
	                  </button>
	                </div>
	              </form>
	            ) : null}
	            <div className="sla-policy-grid">
	              {state.slaPolicies.map((policy) => (
		                <article
		                  className={policy.active ? 'sla-policy-card' : 'sla-policy-card paused'}
		                  key={policy.id}
		                >
	                  <div>
	                    <strong>{policy.name}</strong>
	                    <span>{titleCase(policy.priority)} · {policy.businessHours}</span>
	                  </div>
	                  <small>
	                    {policy.firstResponseMinutes}m first reply · {policy.resolutionMinutes}m resolution
	                  </small>
	                  <div className="tag-list compact-tags">
	                    {policy.channels.slice(0, 5).map((channel) => (
	                      <span key={channel}>{titleCase(channel)}</span>
	                    ))}
	                    {policy.channels.length === 0 ? <span>All channels</span> : null}
	                  </div>
	                  <button
	                    className="secondary-action"
	                    type="button"
	                    onClick={() => void handleToggleSlaPolicy(policy.id, !policy.active)}
	                    disabled={!canManageSlaPolicies || slaPolicyActionBusy}
	                  >
	                    {policy.active ? 'Pause' : 'Reactivate'}
	                  </button>
	                </article>
	              ))}
	            </div>
	          </div>
          <div data-setup-panel="canned" className="automation-settings-panel canned-responses-panel">
            <div className="panel-head compact">
              <div>
                <span>Canned responses</span>
                <h2>Reusable replies agents can insert</h2>
              </div>
              <ClipboardList size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateCannedResponse}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={cannedDraft.name}
                    onChange={(event) => setCannedDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Refund acknowledged"
                    disabled={!canManageUsers || cannedBusy}
                  />
                </label>
                <label>
                  <span>Shortcut</span>
                  <input
                    value={cannedDraft.shortcut}
                    onChange={(event) => setCannedDraft((current) => ({ ...current, shortcut: event.target.value }))}
                    placeholder="/refund"
                    disabled={!canManageUsers || cannedBusy}
                  />
                </label>
              </div>
              <label>
                <span>Reply body</span>
                <textarea
                  required
                  rows={3}
                  value={cannedDraft.body}
                  onChange={(event) => setCannedDraft((current) => ({ ...current, body: event.target.value }))}
                  placeholder="Hi there, thanks for reaching out. We've started your refund…"
                  disabled={!canManageUsers || cannedBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || cannedBusy || cannedDraft.name.trim().length < 2 || cannedDraft.body.trim().length < 2}
              >
                <Plus size={16} />
                Add canned response
              </button>
            </form>
            <div className="canned-response-list">
              {state.responseMacros.length === 0 ? (
                <p className="setup-module-hint">No canned responses yet. Add one agents can reuse.</p>
              ) : (
                state.responseMacros.map((macro) => (
                  <article className={`canned-response-card ${macro.active ? '' : 'inactive'}`} key={macro.id}>
                    {cannedEditId === macro.id ? (
                      <div className="canned-edit">
                        <div className="canned-form-row">
                          <label>
                            <span>Name</span>
                            <input
                              value={cannedEditDraft.name}
                              onChange={(event) =>
                                setCannedEditDraft((current) => ({ ...current, name: event.target.value }))
                              }
                              disabled={cannedBusy}
                            />
                          </label>
                          <label>
                            <span>Shortcut</span>
                            <input
                              value={cannedEditDraft.shortcut}
                              onChange={(event) =>
                                setCannedEditDraft((current) => ({ ...current, shortcut: event.target.value }))
                              }
                              disabled={cannedBusy}
                            />
                          </label>
                        </div>
                        <textarea
                          rows={3}
                          value={cannedEditDraft.body}
                          onChange={(event) =>
                            setCannedEditDraft((current) => ({ ...current, body: event.target.value }))
                          }
                          disabled={cannedBusy}
                        />
                        <div className="canned-card-actions">
                          <button
                            type="button"
                            className="primary-action"
                            disabled={cannedBusy}
                            onClick={() => void saveCannedEdit(macro.id)}
                          >
                            Save
                          </button>
                          <button type="button" className="secondary-action" onClick={() => setCannedEditId('')}>
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="canned-card-head">
                          <div>
                            <strong>{macro.name}</strong>
                            {macro.shortcut ? <code>{macro.shortcut}</code> : null}
                          </div>
                          <span>Used {macro.usageCount}×</span>
                        </div>
                        <p className="canned-card-body">{macro.body}</p>
                        {macro.channels.length > 0 ? (
                          <div className="tag-list compact-tags">
                            {macro.channels.slice(0, 5).map((channel) => (
                              <span key={channel}>{titleCase(channel)}</span>
                            ))}
                          </div>
                        ) : null}
                        <div className="canned-card-actions">
                          <button
                            type="button"
                            className="secondary-action"
                            disabled={!canManageUsers}
                            onClick={() => startEditCanned(macro)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="secondary-action"
                            disabled={!canManageUsers || cannedBusy}
                            onClick={() => void toggleCannedResponse(macro)}
                          >
                            {macro.active ? 'Pause' : 'Activate'}
                          </button>
                        </div>
                      </>
                    )}
                  </article>
                ))
              )}
            </div>
          </div>
          <div data-setup-panel="templates" className="automation-settings-panel ticket-templates-panel">
            <div className="panel-head compact">
              <div>
                <span>Ticket templates</span>
                <h2>Pre-filled tickets agents can start from</h2>
              </div>
              <ClipboardList size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateTicketTemplate}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={templateDraft.name}
                    onChange={(event) => setTemplateDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Refund request"
                    disabled={!canManageUsers || templateBusy}
                  />
                </label>
                <label>
                  <span>Priority</span>
                  <select
                    value={templateDraft.priority}
                    onChange={(event) =>
                      setTemplateDraft((current) => ({ ...current, priority: event.target.value as Priority }))
                    }
                    disabled={!canManageUsers || templateBusy}
                  >
                    {priorityOptions
                      .filter((option): option is Priority => option !== 'all')
                      .map((priority) => (
                        <option key={priority} value={priority}>{titleCase(priority)}</option>
                      ))}
                  </select>
                </label>
              </div>
              <div className="canned-form-row">
                <label>
                  <span>Subject</span>
                  <input
                    required
                    value={templateDraft.subject}
                    onChange={(event) => setTemplateDraft((current) => ({ ...current, subject: event.target.value }))}
                    placeholder="Refund request for booking"
                    disabled={!canManageUsers || templateBusy}
                  />
                </label>
                <label>
                  <span>Group</span>
                  <select
                    value={templateDraft.group}
                    onChange={(event) => setTemplateDraft((current) => ({ ...current, group: event.target.value }))}
                    disabled={!canManageUsers || templateBusy}
                  >
                    <option value="">Unassigned</option>
                    {state.supportGroups.map((group) => (
                      <option key={group.id} value={group.name}>{group.name}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label>
                <span>Tags (comma separated)</span>
                <input
                  value={templateDraft.tags}
                  onChange={(event) => setTemplateDraft((current) => ({ ...current, tags: event.target.value }))}
                  placeholder="refund, billing"
                  disabled={!canManageUsers || templateBusy}
                />
              </label>
              <label>
                <span>Description</span>
                <textarea
                  rows={3}
                  value={templateDraft.description}
                  onChange={(event) => setTemplateDraft((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Steps the agent should confirm before sending…"
                  disabled={!canManageUsers || templateBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || templateBusy || templateDraft.name.trim().length < 2 || templateDraft.subject.trim().length < 1}
              >
                <Plus size={16} />
                Add template
              </button>
            </form>
            <div className="canned-response-list">
              {state.ticketTemplates.length === 0 ? (
                <p className="setup-module-hint">No ticket templates yet. Add one agents can start from.</p>
              ) : (
                state.ticketTemplates.map((template) => (
                  <article className={`canned-response-card ${template.active ? '' : 'inactive'}`} key={template.id}>
                    <div className="canned-card-head">
                      <div>
                        <strong>{template.name}</strong>
                        <span className={`template-priority priority-${template.priority}`}>
                          {titleCase(template.priority)}
                        </span>
                      </div>
                      <span>{template.group || 'Unassigned'}</span>
                    </div>
                    <p className="canned-card-body">
                      <b>{template.subject}</b>
                      {template.description ? ` — ${template.description}` : ''}
                    </p>
                    {template.tags.length > 0 ? (
                      <div className="tag-list compact-tags">
                        {template.tags.slice(0, 6).map((tag) => (
                          <span key={tag}>{tag}</span>
                        ))}
                      </div>
                    ) : null}
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || templateBusy}
                        onClick={() => void toggleTicketTemplate(template)}
                      >
                        {template.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
          <div data-setup-panel="tags" className="automation-settings-panel tags-panel">
            <div className="panel-head compact">
              <div>
                <span>Tags</span>
                <h2>Canonical labels agents apply to tickets</h2>
              </div>
              <Filter size={18} />
            </div>
            <form className="user-create-form tag-form" onSubmit={handleCreateTag}>
              <label className="tag-color-field">
                <span>Color</span>
                <input
                  type="color"
                  value={tagDraft.color}
                  onChange={(event) => setTagDraft((current) => ({ ...current, color: event.target.value }))}
                  disabled={!canManageUsers || tagBusy}
                  aria-label="Tag color"
                />
              </label>
              <label>
                <span>Name</span>
                <input
                  required
                  value={tagDraft.name}
                  onChange={(event) => setTagDraft((current) => ({ ...current, name: event.target.value }))}
                  placeholder="vip"
                  disabled={!canManageUsers || tagBusy}
                />
              </label>
              <label>
                <span>Description</span>
                <input
                  value={tagDraft.description}
                  onChange={(event) => setTagDraft((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Premium customers"
                  disabled={!canManageUsers || tagBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || tagBusy || tagDraft.name.trim().length < 1}
              >
                <Plus size={16} />
                Add tag
              </button>
            </form>
            <div className="tag-admin-list">
              {state.tags.length === 0 ? (
                <p className="setup-module-hint">No tags yet. Add labels agents can apply.</p>
              ) : (
                state.tags.map((tag) => (
                  <article className={`tag-admin-card ${tag.active ? '' : 'inactive'}`} key={tag.id}>
                    <span className="tag-swatch" style={{ background: tag.color }} />
                    <div className="tag-admin-info">
                      <strong>{tag.name}</strong>
                      {tag.description ? <span>{tag.description}</span> : null}
                    </div>
                    <button
                      type="button"
                      className="secondary-action"
                      disabled={!canManageUsers || tagBusy}
                      onClick={() => void toggleTag(tag)}
                    >
                      {tag.active ? 'Pause' : 'Activate'}
                    </button>
                  </article>
                ))
              )}
            </div>
          </div>
          <div data-setup-panel="csat" className="automation-settings-panel csat-surveys-panel">
            <div className="panel-head compact">
              <div>
                <span>CSAT surveys</span>
                <h2>Satisfaction surveys sent after resolution</h2>
              </div>
              <Star size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateCsatSurvey}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={surveyDraft.name}
                    onChange={(event) => setSurveyDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Ticket resolution survey"
                    disabled={!canManageUsers || surveyBusy}
                  />
                </label>
                <label>
                  <span>Scale (max rating)</span>
                  <select
                    value={surveyDraft.scale}
                    onChange={(event) => setSurveyDraft((current) => ({ ...current, scale: Number(event.target.value) }))}
                    disabled={!canManageUsers || surveyBusy}
                  >
                    {[3, 4, 5, 7, 10].map((scale) => (
                      <option key={scale} value={scale}>{scale}-point</option>
                    ))}
                  </select>
                </label>
              </div>
              <label>
                <span>Question</span>
                <input
                  required
                  value={surveyDraft.question}
                  onChange={(event) => setSurveyDraft((current) => ({ ...current, question: event.target.value }))}
                  placeholder="How satisfied were you with our support?"
                  disabled={!canManageUsers || surveyBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || surveyBusy || surveyDraft.name.trim().length < 2 || surveyDraft.question.trim().length < 2}
              >
                <Plus size={16} />
                Add survey
              </button>
            </form>
            <div className="canned-response-list">
              {state.csatSurveys.length === 0 ? (
                <p className="setup-module-hint">No CSAT surveys yet. Add one to collect satisfaction ratings.</p>
              ) : (
                state.csatSurveys.map((survey) => (
                  <article className={`canned-response-card ${survey.active ? '' : 'inactive'}`} key={survey.id}>
                    <div className="canned-card-head">
                      <div>
                        <strong>{survey.name}</strong>
                        <span className="template-priority">{survey.scale}-point</span>
                      </div>
                      <span>
                        {survey.channels.length > 0
                          ? survey.channels.map((channel) => titleCase(channel)).join(', ')
                          : 'All channels'}
                      </span>
                    </div>
                    <p className="canned-card-body">{survey.question}</p>
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || surveyBusy}
                        onClick={() => void toggleCsatSurvey(survey)}
                      >
                        {survey.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
          <div data-setup-panel="email-notifications" className="automation-settings-panel email-notifications-panel">
            <div className="panel-head compact">
              <div>
                <span>Email notifications</span>
                <h2>Automatic emails on ticket lifecycle events</h2>
              </div>
              <Mail size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateEmailNotification}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={notifDraft.name}
                    onChange={(event) => setNotifDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="New ticket acknowledgement"
                    disabled={!canManageUsers || notifBusy}
                  />
                </label>
                <label>
                  <span>Trigger event</span>
                  <select
                    value={notifDraft.event}
                    onChange={(event) => setNotifDraft((current) => ({ ...current, event: event.target.value }))}
                    disabled={!canManageUsers || notifBusy}
                  >
                    <option value="ticket_created">Ticket created</option>
                    <option value="ticket_assigned">Ticket assigned</option>
                    <option value="ticket_replied">Agent replied</option>
                    <option value="ticket_resolved">Ticket resolved</option>
                    <option value="sla_breach">SLA breach</option>
                  </select>
                </label>
              </div>
              <label>
                <span>Recipients (comma separated)</span>
                <input
                  value={notifDraft.recipients}
                  onChange={(event) => setNotifDraft((current) => ({ ...current, recipients: event.target.value }))}
                  placeholder="requester, assignee, supervisor"
                  disabled={!canManageUsers || notifBusy}
                />
              </label>
              <label>
                <span>Subject</span>
                <input
                  value={notifDraft.subject}
                  onChange={(event) => setNotifDraft((current) => ({ ...current, subject: event.target.value }))}
                  placeholder="We've received your request"
                  disabled={!canManageUsers || notifBusy}
                />
              </label>
              <label>
                <span>Body</span>
                <textarea
                  rows={3}
                  value={notifDraft.body}
                  onChange={(event) => setNotifDraft((current) => ({ ...current, body: event.target.value }))}
                  placeholder="Hi {{name}}, thanks for contacting support…"
                  disabled={!canManageUsers || notifBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || notifBusy || notifDraft.name.trim().length < 2}
              >
                <Plus size={16} />
                Add notification
              </button>
            </form>
            <div className="canned-response-list">
              {state.emailNotifications.length === 0 ? (
                <p className="setup-module-hint">No email notifications yet. Add lifecycle emails.</p>
              ) : (
                state.emailNotifications.map((notification) => (
                  <article
                    className={`canned-response-card ${notification.active ? '' : 'inactive'}`}
                    key={notification.id}
                  >
                    <div className="canned-card-head">
                      <div>
                        <strong>{notification.name}</strong>
                        <span className="template-priority">{titleCase(notification.event.replace(/_/g, ' '))}</span>
                      </div>
                      <span>
                        {notification.recipients.length > 0
                          ? notification.recipients.join(', ')
                          : 'No recipients'}
                      </span>
                    </div>
                    {notification.subject ? (
                      <p className="canned-card-body">
                        <b>{notification.subject}</b>
                        {notification.body ? ` — ${notification.body}` : ''}
                      </p>
                    ) : notification.body ? (
                      <p className="canned-card-body">{notification.body}</p>
                    ) : null}
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || notifBusy}
                        onClick={() => void toggleEmailNotification(notification)}
                      >
                        {notification.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
          <div data-setup-panel="scenario" className="automation-settings-panel scenario-automations-panel">
            <div className="panel-head compact">
              <div>
                <span>Scenario automations</span>
                <h2>One-click action bundles agents run on a ticket</h2>
              </div>
              <Workflow size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateScenarioAutomation}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={scenarioDraft.name}
                    onChange={(event) => setScenarioDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Start refund flow"
                    disabled={!canManageUsers || scenarioBusy}
                  />
                </label>
                <label>
                  <span>Description</span>
                  <input
                    value={scenarioDraft.description}
                    onChange={(event) => setScenarioDraft((current) => ({ ...current, description: event.target.value }))}
                    placeholder="Tag, prioritise, and route refunds"
                    disabled={!canManageUsers || scenarioBusy}
                  />
                </label>
              </div>
              <div className="scenario-action-builder">
                <span className="scenario-builder-label">Actions</span>
                {scenarioActions.length > 0 ? (
                  <ul className="scenario-action-list">
                    {scenarioActions.map((action, index) => (
                      <li key={`${action.type}-${index}`}>
                        <span>{scenarioActionLabel(action.type)}: <b>{action.value}</b></span>
                        <button type="button" aria-label="Remove action" onClick={() => removeScenarioAction(index)}>
                          <X size={13} />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <div className="scenario-action-row">
                  <select
                    value={scenarioActionDraft.type}
                    onChange={(event) => setScenarioActionDraft((current) => ({ ...current, type: event.target.value }))}
                    disabled={!canManageUsers || scenarioBusy}
                    aria-label="Action type"
                  >
                    {scenarioActionTypes.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                  <input
                    value={scenarioActionDraft.value}
                    onChange={(event) => setScenarioActionDraft((current) => ({ ...current, value: event.target.value }))}
                    placeholder="Value (e.g. refund, high, Refund Desk)"
                    disabled={!canManageUsers || scenarioBusy}
                    aria-label="Action value"
                  />
                  <button
                    type="button"
                    className="secondary-action"
                    onClick={addScenarioAction}
                    disabled={!canManageUsers || scenarioBusy || scenarioActionDraft.value.trim().length === 0}
                  >
                    <Plus size={14} />
                    Add action
                  </button>
                </div>
              </div>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || scenarioBusy || scenarioDraft.name.trim().length < 2 || scenarioActions.length === 0}
              >
                <Plus size={16} />
                Add scenario
              </button>
            </form>
            <div className="canned-response-list">
              {state.scenarioAutomations.length === 0 ? (
                <p className="setup-module-hint">No scenario automations yet. Build a one-click action bundle.</p>
              ) : (
                state.scenarioAutomations.map((scenario) => (
                  <article className={`canned-response-card ${scenario.active ? '' : 'inactive'}`} key={scenario.id}>
                    <div className="canned-card-head">
                      <div>
                        <strong>{scenario.name}</strong>
                        <span className="template-priority">{scenario.actions.length} actions</span>
                      </div>
                    </div>
                    {scenario.description ? <p className="canned-card-body">{scenario.description}</p> : null}
                    <div className="tag-list compact-tags">
                      {scenario.actions.map((action, index) => (
                        <span key={`${action.type}-${index}`}>
                          {scenarioActionLabel(action.type)}: {action.value}
                        </span>
                      ))}
                    </div>
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || scenarioBusy}
                        onClick={() => void toggleScenarioAutomation(scenario)}
                      >
                        {scenario.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
          <button className="secondary-action" type="button" onClick={resetDemo}>
            <RotateCcw size={16} />
            Reset review data
          </button>
          </>
          ) : null}
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

  // Kept callable while the ticket list is the default Freshdesk-style inbox.
  void renderFilters
  void renderConversationRow

  const currentScreen = screenConfig.find((item) => item.id === state.selectedScreen) ?? screenConfig[0]
  const CurrentScreenIcon = currentScreen.icon
  const pageTitle =
    currentScreen.id === 'command'
      ? 'Omnichannel Dashboard'
      : currentScreen.id === 'inbox'
        ? 'All tickets'
        : currentScreen.id === 'knowledge'
          ? 'Knowledge base (Wakanow)'
          : currentScreen.id === 'channels'
            ? 'Omnichat'
            : currentScreen.label
  const pageSubtitle = currentMarket ? `${currentMarket.name} market. ${screenLead[currentScreen.id]}` : screenLead[currentScreen.id]

  return (
    <div className={`app-shell ${navExpanded ? 'nav-expanded' : 'nav-collapsed'}`}>
      <aside className="sidebar">
        <div className="sidebar-head">
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
          <button
            type="button"
            className="sidebar-toggle"
            onClick={toggleNav}
            aria-pressed={navExpanded}
            aria-label={navExpanded ? 'Collapse navigation' : 'Expand navigation'}
            title={navExpanded ? 'Collapse navigation' : 'Expand navigation'}
          >
            <ArrowRight className={navExpanded ? 'flip-x' : ''} size={16} />
          </button>
        </div>
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
        {!announcementDismissed ? (
          <div className="omni-ai-announcement" aria-label="Omni AI announcement">
            <Sparkles size={16} />
            <span>Introducing Omni AI Agents: Your intelligent support representative</span>
            <button type="button" onClick={() => selectScreen('automation')}>Explore AI Agent</button>
            <i />
            <button type="button" onClick={() => selectScreen('analytics')}>AI analytics</button>
            <button
              type="button"
              aria-label="Dismiss announcement"
              onClick={() => setAnnouncementDismissed(true)}
            >
              <X size={14} />
            </button>
          </div>
        ) : null}
        <header className="topbar omni-desk-topbar" aria-label={pageSubtitle}>
          <div className="omni-page-title">
            <button className="desk-product-icon" type="button" aria-label={pageTitle}>
              <CurrentScreenIcon size={16} />
            </button>
            <h1>{pageTitle}</h1>
            {currentScreen.id === 'inbox' && <span className="count-pill">{state.conversations.length}</span>}
          </div>
          <div className="topbar-actions">
            <button className="desk-top-action" type="button" onClick={() => openQuickCreate('email')}>
              <Plus size={14} />
              New
              <ChevronDown size={13} />
            </button>
            <div className="omni-search-button-wrap">
              <button className="desk-top-action" type="button" onClick={() => setGlobalSearchOpen((value) => !value)}>
                <Search size={14} />
                Search
              </button>
              {globalSearchOpen && (
                <div className="omni-search-popover">
                  <div className="global-search active">
                    <Search size={16} />
                    <input
                      value={state.filters.search}
                      onFocus={() => setGlobalSearchOpen(true)}
                      onChange={(event) => {
                        const nextSearch = event.target.value
                        setFilters({ search: nextSearch })
                        if (nextSearch.trim().length < 2) {
                          setGlobalSearchResults([])
                          setGlobalSearchError('')
                          setGlobalSearchLoading(false)
                        }
                        setGlobalSearchOpen(true)
                      }}
                      placeholder="Search tickets, customers, teams"
                      aria-label="Global search"
                    />
                    {renderGlobalSearchResults()}
                  </div>
                </div>
              )}
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
            <button className="desk-top-action" type="button" onClick={() => selectScreen('knowledge')}>
              Help
            </button>
            <button className="desk-top-action" type="button" onClick={() => setSetupSection('connectors')}>
              Apps
            </button>
            <div className="desk-user-menu">
              <button
                className="desk-user-pill"
                type="button"
                aria-expanded={userMenuOpen}
                aria-haspopup="menu"
                onClick={() => setUserMenuOpen((open) => !open)}
              >
                {initials(backendSession.user.name)}
              </button>
              {userMenuOpen ? (
                <div className="desk-user-dropdown" role="menu">
                  <div className="desk-user-dropdown-head">
                    <strong>{backendSession.user.name}</strong>
                    <span>{backendSession.user.email}</span>
                  </div>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setUserMenuOpen(false)
                      selectScreen('admin')
                    }}
                  >
                    <Settings size={14} />
                    Settings
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setUserMenuOpen(false)
                      void logout()
                    }}
                  >
                    <X size={14} />
                    Sign out
                  </button>
                </div>
              ) : null}
            </div>
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
