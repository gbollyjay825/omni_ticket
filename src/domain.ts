export type ChannelId =
  | 'email'
  | 'chat'
  | 'phone'
  | 'whatsapp'
  | 'sms'
  | 'instagram'
  | 'facebook'
  | 'portal'
  | 'api'
  | 'internal'

export type ChannelStatus = 'healthy' | 'degraded' | 'paused'
export type ConversationStatus = 'new' | 'open' | 'pending' | 'waiting' | 'resolved'
export type Priority = 'urgent' | 'high' | 'medium' | 'low'
export type Sentiment = 'positive' | 'neutral' | 'frustrated' | 'at-risk'
export type SlaState = 'healthy' | 'risk' | 'breached' | 'paused'
export type TimelineType =
  | 'customer-message'
  | 'agent-reply'
  | 'internal-note'
  | 'handoff'
  | 'voice-log'
  | 'chat-transcript'
  | 'social-dm'
  | 'portal-comment'
  | 'api-event'
  | 'automation'
export type ComposerMode = 'reply' | 'note' | 'handoff'
export type AgentAvailability = 'available' | 'busy' | 'away' | 'offline'
export type ArticleStatus = 'draft' | 'review' | 'published'
export type RuleStatus = 'active' | 'paused' | 'failing'
export type TrackerStatus = 'done' | 'in-progress' | 'pending' | 'blocked'
export type HandoffStatus = 'requested' | 'accepted' | 'in-progress' | 'blocked' | 'completed'
export type TicketFieldType = 'text' | 'textarea' | 'select' | 'multiselect' | 'checkbox' | 'number' | 'date'

export interface Channel {
  id: ChannelId
  label: string
  shortLabel: string
  status: ChannelStatus
  queueDepth: number
  activeSessions: number
  avgWaitMinutes: number
  targetMinutes: number
  slaRisk: number
  health: number
  intakeEnabled: boolean
  description: string
}

export interface TimelineEvent {
  id: string
  type: TimelineType
  channelId: ChannelId
  author: string
  authorRole: 'customer' | 'agent' | 'system' | 'partner'
  timestamp: string
  body: string
  deliveryState?: 'queued' | 'sending' | 'sent' | 'failed' | 'retrying' | 'dead_lettered'
}

export interface Task {
  id: string
  label: string
  done: boolean
}

export interface CopilotRecommendation {
  summary: string
  intent: string
  sentiment: Sentiment
  autoTags: string[]
  slaReason: string
  suggestedReply: string
  suggestedArticle: string
  escalation: string
  recommendedAction: string
  confidence: number
  knowledgeReasons?: string[]
  responseMacros?: ResponseMacroSuggestion[]
  duplicateSuggestions?: DuplicateTicketSuggestion[]
}

export interface ResponseMacro {
  id: string
  name: string
  body: string
  language: string
  channels: ChannelId[]
  tags: string[]
  shortcut?: string
  active: boolean
  usageCount: number
  lastUsedAt?: string
  updatedAt: string
}

export interface ResponseMacroSuggestion {
  macro: ResponseMacro
  score: number
  reasons: string[]
  matchedTerms: string[]
}

export interface DuplicateTicketSuggestion {
  ticketId: string
  ticketNumber: string
  subject: string
  status: ConversationStatus
  priority: Priority
  channelId: ChannelId
  customerName: string
  customerEmail: string
  score: number
  reasons: string[]
  matchedTerms: string[]
  updatedAt: string
}

export interface OmniConversation {
  id: string
  ticketNumber: string
  customerId: string
  channelId: ChannelId
  subject: string
  preview: string
  status: ConversationStatus
  priority: Priority
  sentiment: Sentiment
  intent: string
  group: string
  assigneeId: string
  createdAt: string
  updatedAt: string
  firstResponseDue: string
  resolutionDue: string
  slaState: SlaState
  language: string
  unread: boolean
  tags: string[]
  customFields: Record<string, unknown>
  tasks: Task[]
  timeline: TimelineEvent[]
  copilot: CopilotRecommendation
}

export interface TicketField {
  id: string
  key: string
  label: string
  fieldType: TicketFieldType
  required: boolean
  active: boolean
  system: boolean
  options: string[]
  channels: ChannelId[]
  placeholder: string
  helpText: string
  position: number
  updatedAt: string
}

export interface SupportGroup {
  id: string
  name: string
  description: string
  teamEmail?: string | null
  active: boolean
  channels: ChannelId[]
  skills: string[]
  memberCount: number
  openTicketCount: number
  slaRiskCount: number
  updatedAt: string
}

export interface ContactMethod {
  type: 'email' | 'phone' | 'whatsapp' | 'sms' | 'social' | 'portal'
  label: string
  value: string
  primary?: boolean
}

export interface CustomerProfile {
  id: string
  name: string
  company: string
  title: string
  email: string
  phone: string
  location: string
  healthScore: number
  csat: number
  totalConversations: number
  openValue: string
  preferredChannels: ChannelId[]
  contactMethods: ContactMethod[]
  tags: string[]
  recentActivity: string
}

export interface AgentProfile {
  id: string
  name: string
  role: string
  avatar: string
  availability: AgentAvailability
  skills: string[]
  load: number
  capacity: number
  occupancy: number
  csat: number
  shift: string
}

export interface KnowledgeArticle {
  id: string
  title: string
  category: string
  status: ArticleStatus
  language: string
  helpfulness: number
  deflection: number
  ownerId: string
  intents: string[]
  updatedAt: string
}

export interface AutomationRule {
  id: string
  name: string
  trigger: string
  condition: string
  action: string
  owner: string
  status: RuleStatus
  health: number
  lastFired: string
  failures: number
}

export interface SlaPolicy {
  id: string
  name: string
  active: boolean
  channels: ChannelId[]
  priority: Priority
  firstResponseMinutes: number
  resolutionMinutes: number
  businessHours: string
  position: number
  updatedAt: string
}

export interface BusinessHoursDay {
  day: string
  enabled: boolean
  open: string
  close: string
}

export interface BusinessHours {
  id: string
  name: string
  timezone: string
  active: boolean
  days: BusinessHoursDay[]
  updatedAt: string
}

export interface TicketTemplate {
  id: string
  name: string
  subject: string
  description: string
  priority: Priority
  channelId: ChannelId
  group: string
  tags: string[]
  active: boolean
  updatedAt: string
}

export interface Tag {
  id: string
  name: string
  color: string
  description: string
  active: boolean
  updatedAt: string
}

export interface CsatSurvey {
  id: string
  name: string
  question: string
  scale: number
  channels: ChannelId[]
  active: boolean
  updatedAt: string
}

export interface EmailNotification {
  id: string
  name: string
  event: string
  recipients: string[]
  subject: string
  body: string
  active: boolean
  updatedAt: string
}

export interface ScenarioAction {
  type: string
  value: string
}

export interface ScenarioAutomation {
  id: string
  name: string
  description: string
  actions: ScenarioAction[]
  active: boolean
  updatedAt: string
}

export interface CustomFieldDefinition {
  id: string
  entity: string
  key: string
  label: string
  fieldType: TicketFieldType
  required: boolean
  active: boolean
  options: string[]
  helpText: string
  position: number
  updatedAt: string
}

export interface OutboxItem {
  id: string
  conversationId: string
  channelId: ChannelId
  mode: ComposerMode
  body: string
  createdAt: string
  state: 'queued' | 'ready'
}

export interface HandoffRecord {
  id: string
  conversationId: string
  linkedConversationId?: string
  ticketNumber: string
  customerId: string
  sourceTeam: string
  receivingTeam: string
  requesterId: string
  ownerId: string
  reason: string
  context: string
  customerImpact: string
  acceptanceCriteria: string
  status: HandoffStatus
  priority: Priority
  dueAt: string
  createdAt: string
  updatedAt: string
  checklist: Task[]
  blockers: string[]
}

export interface Epic {
  id: string
  title: string
  outcome: string
  status: TrackerStatus
  pending: string
  progress: number
}

export interface BacklogItem {
  id: string
  title: string
  priority: 'P0' | 'P1' | 'P2'
  status: TrackerStatus
  epicId: string
}

export interface Issue {
  id: string
  title: string
  status: 'closed' | 'pending'
  closedOn?: string
}

export interface WorkspaceSettings {
  aiWorkQueueAutomationEnabled: boolean
}

export interface AttachmentDraft {
  filename: string
  contentType: string
  sizeBytes: number
  file?: File
}

export interface InboxFilters {
  channel: ChannelId | 'all'
  status: ConversationStatus | 'all'
  priority: Priority | 'all'
  sla: SlaState | 'all'
  assignee: string | 'all'
  sentiment: Sentiment | 'all'
  search: string
}

export interface OmniState {
  version: number
  selectedScreen: ScreenId
  selectedConversationId: string
  selectedCustomerId: string
  selectedChannelId: ChannelId | 'all'
  filters: InboxFilters
  channels: Channel[]
  conversations: OmniConversation[]
  customers: CustomerProfile[]
  agents: AgentProfile[]
  supportGroups: SupportGroup[]
  articles: KnowledgeArticle[]
  ticketFields: TicketField[]
  responseMacros: ResponseMacro[]
  rules: AutomationRule[]
  slaPolicies: SlaPolicy[]
  businessHours: BusinessHours[]
  ticketTemplates: TicketTemplate[]
  tags: Tag[]
  csatSurveys: CsatSurvey[]
  emailNotifications: EmailNotification[]
  scenarioAutomations: ScenarioAutomation[]
  customFieldDefinitions: CustomFieldDefinition[]
  handoffs: HandoffRecord[]
  outbox: OutboxItem[]
  settings: WorkspaceSettings
  epics: Epic[]
  backlog: BacklogItem[]
  issues: Issue[]
}

export type ScreenId =
  | 'command'
  | 'inbox'
  | 'channels'
  | 'customers'
  | 'knowledge'
  | 'automation'
  | 'handoffs'
  | 'analytics'
  | 'workforce'
  | 'admin'
  | 'portal'
  | 'tracker'

export interface ComposerInput {
  conversationId: string
  mode: ComposerMode
  channelId: ChannelId
  body: string
  online: boolean
  handoffTeam?: string
  handoffReason?: string
  attachment?: AttachmentDraft
}

export interface NewTicketInput {
  customerId: string
  channelId: ChannelId
  subject: string
  body: string
  priority: Priority
  group: string
  assigneeId: string
  customFields?: Record<string, unknown>
}
