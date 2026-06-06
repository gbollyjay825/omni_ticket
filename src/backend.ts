export interface BackendHealth {
  status: string
}

export interface BackendSettings {
  market_id: string
  ai_work_queue_automation_enabled: boolean
  ai_can_send_customer_messages: boolean
  default_timezone: string
  business_hours: string
  public_brand_name: string
}

export interface BackendAnalyticsSummary {
  open_tickets: number
  at_risk_tickets: number
  breached_tickets: number
  channel_volume?: Record<string, number>
  active_agents?: number
  avg_occupancy?: number
  avg_csat?: number | null
}

export interface BackendAnalyticsRollup {
  id: string
  market_id: string
  period_start: string
  period_end: string
  open_tickets: number
  at_risk_tickets: number
  breached_tickets: number
  active_agents: number
  avg_occupancy: number
  avg_csat: number | null
  channel_volume: Record<string, number>
  created_at: string
  updated_at: string
}

export interface BackendCsatFeedback {
  id: string
  market_id: string
  ticket_id: string
  customer_id: string
  rating: number
  comment: string | null
  source: 'customer_survey' | 'agent_recorded' | 'service_import'
  submitted_by: string | null
  created_at: string
  updated_at: string
}

export interface BackendAuditEvent {
  id: string
  market_id: string | null
  actor: string
  action: string
  entity_type: string
  entity_id: string
  created_at: string
  details: Record<string, unknown>
}

export interface BackendAuditRetentionPolicy {
  market_id: string
  retention_days: number
  cutoff_at: string
  retained_events: number
  prunable_events: number
  export_max_rows: number
}

export interface BackendAuditRetentionResult {
  policy: BackendAuditRetentionPolicy
  deleted_events: number
  audit_event_id: string | null
}

export type BackendAuditExportFormat = 'csv' | 'json'

export interface BackendAuditExportOptions {
  format: BackendAuditExportFormat
  actor?: string
  action?: string
  entity_type?: string
  entity_id?: string
  since?: string
  until?: string
  limit?: number
}

export interface BackendAuditExport {
  content: string
  contentType: string
  filename: string
}

export interface BackendConnectorProvider {
  provider: string
  status: string
  market: string
  account: string | null
  production_dependencies: string[]
  supports: string[]
  intake_enabled?: boolean
  outbound_enabled?: boolean
  webhook_verified?: boolean
  secret_configured?: boolean
  failure_count?: number
}

export interface BackendConnectorAccount {
  id: string
  market_id: string
  provider: string
  display_name: string
  account_identifier: string
  status:
    | 'mocked'
    | 'connected'
    | 'pending_credentials'
    | 'action_required'
    | 'disabled'
    | 'error'
  intake_enabled: boolean
  outbound_enabled: boolean
  webhook_url: string
  webhook_verified: boolean
  credential_ref: string | null
  secret_configured: boolean
  last_sync_at: string | null
  last_error: string | null
  failure_count: number
  required_credentials: string[]
  capabilities: string[]
  created_at: string
  updated_at: string
}

export interface BackendOutboundMessage {
  id: string
  market_id: string
  ticket_id: string
  timeline_event_id: string | null
  connector_event_id: string | null
  provider: string
  status: 'queued' | 'sending' | 'sent' | 'failed' | 'retrying' | 'dead_lettered'
  actor: string
  body: string
  idempotency_key: string
  attempts: number
  max_attempts: number
  next_attempt_at: string | null
  sent_at: string | null
  last_error: string | null
  payload: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type BackendOperationalAlertSeverity = 'info' | 'warning' | 'critical'
export type BackendOperationalAlertStatus = 'open' | 'acknowledged' | 'resolved'

export interface BackendOperationalAlert {
  id: string
  market_id: string
  severity: BackendOperationalAlertSeverity
  status: BackendOperationalAlertStatus
  source: string
  entity_type: string
  entity_id: string
  dedupe_key: string
  title: string
  message: string
  details: Record<string, unknown>
  occurrence_count: number
  first_seen_at: string
  last_seen_at: string
  acknowledged_at: string | null
  acknowledged_by: string | null
  resolved_at: string | null
  resolved_by: string | null
  created_at: string
  updated_at: string
}

export interface BackendOperationalAlertDelivery {
  id: string
  market_id: string
  alert_id: string
  destination_type: string
  destination_name: string
  status: 'queued' | 'sending' | 'sent' | 'failed'
  attempts: number
  max_attempts: number
  next_attempt_at: string | null
  sent_at: string | null
  last_error: string | null
  payload: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface BackendOperationalAlertDeliveryConfig {
  webhook_configured: boolean
  destination_type: string
  destination_name: string
  min_severity: BackendOperationalAlertSeverity
  max_attempts: number
}

export interface BackendProductionAccountRequestItem {
  id: string
  area: string
  provider: string
  purpose: string
  backend_use: string
  status: 'ready' | 'missing' | 'action_required'
  required_credentials: string[]
  missing_settings: string[]
  callback_urls: string[]
  setup_location: string
  credential_reference_name: string
  account_owner: string
  notes: string
}

export interface BackendProductionAccountRequestPack {
  market_id: string
  recipient_email: string
  generated_at: string
  total_items: number
  ready_items: number
  missing_items: number
  subject: string
  body: string
  mailto_url: string
  items: BackendProductionAccountRequestItem[]
}

export interface BackendProductionAccountRequestDelivery {
  pack: BackendProductionAccountRequestPack
  outbound_message: BackendOutboundMessage
  ticket_id: string
  ticket_public_id: string
  already_queued: boolean
  queued_at: string
}

export type BackendProductionAccountReferenceStatus =
  | 'requested'
  | 'provisioned'
  | 'connected'
  | 'blocked'
  | 'retired'

export interface BackendProductionAccountReference {
  id: string
  market_id: string
  provider: string
  area: string
  account_name: string
  account_identifier: string
  status: BackendProductionAccountReferenceStatus
  owner_email: string | null
  credential_reference: string
  docs_reference: string
  callback_urls: string[]
  notes: string
  created_by: string
  updated_by: string
  created_at: string
  updated_at: string
}

export interface BackendProductionAccountReferenceDocs {
  market_id: string
  markdown: string
  generated_at: string
}

export interface BackendProductionReadinessItem {
  id: string
  category: string
  label: string
  status: 'ready' | 'action_required' | 'blocked'
  summary: string
  evidence: string[]
  next_action: string
  docs_reference: string
}

export interface BackendProductionReadinessChecklist {
  market_id: string
  generated_at: string
  overall_status: 'ready' | 'action_required' | 'blocked'
  total_items: number
  ready_items: number
  action_items: number
  blocked_items: number
  items: BackendProductionReadinessItem[]
}

export interface BackendCreateProductionAccountReferenceInput {
  provider: string
  area: string
  account_name: string
  account_identifier?: string
  status?: BackendProductionAccountReferenceStatus
  owner_email?: string | null
  credential_reference?: string
  docs_reference?: string
  callback_urls?: string[]
  notes?: string
}

export type BackendUpdateProductionAccountReferenceInput =
  Partial<BackendCreateProductionAccountReferenceInput>

export interface BackendSupervisorRecommendation {
  id: string
  market_id: string
  title: string
  summary: string
  action: string
  severity: BackendOperationalAlertSeverity
  category: string
  priority_score: number
  ticket_id: string | null
  handoff_id: string | null
  support_group: string | null
  owner_id: string | null
  reasons: string[]
  created_at: string
}

export interface BackendOutboundProviderConfig {
  provider: string
  adapter: string
  configured: boolean
  live_delivery: boolean
  fallback_adapter: string | null
  required_settings: string[]
  missing_settings: string[]
  notes: string
}

export interface BackendInboundProviderConfig {
  provider: string
  adapter: string
  configured: boolean
  live_intake: boolean
  polling_enabled: boolean
  required_settings: string[]
  missing_settings: string[]
  notes: string
}

export interface BackendAttachmentProviderConfig {
  storage_backend: string
  storage_configured: boolean
  storage_live: boolean
  scanner_adapter: string
  scanner_configured: boolean
  live_scanning: boolean
  required_settings: string[]
  missing_settings: string[]
  notes: string
}

export interface BackendEmailProviderSettings {
  market_id: string
  inbound_enabled: boolean
  inbound_host: string
  inbound_port: number
  inbound_username: string
  inbound_mailbox: string
  inbound_use_ssl: boolean
  inbound_mark_seen: boolean
  inbound_password_configured: boolean
  outbound_enabled: boolean
  outbound_host: string
  outbound_port: number
  outbound_username: string
  outbound_from_email: string
  outbound_use_starttls: boolean
  outbound_use_ssl: boolean
  outbound_password_configured: boolean
  updated_at: string
}

export interface BackendUpdateEmailProviderSettingsInput {
  inbound_enabled?: boolean
  inbound_host?: string
  inbound_port?: number
  inbound_username?: string
  inbound_password?: string
  inbound_mailbox?: string
  inbound_use_ssl?: boolean
  inbound_mark_seen?: boolean
  clear_inbound_password?: boolean
  outbound_enabled?: boolean
  outbound_host?: string
  outbound_port?: number
  outbound_username?: string
  outbound_password?: string
  outbound_from_email?: string
  outbound_use_starttls?: boolean
  outbound_use_ssl?: boolean
  clear_outbound_password?: boolean
}

export interface BackendIntegrationCredentialSettings {
  market_id: string
  ai_provider: string
  anthropic_api_base_url: string
  anthropic_model: string
  anthropic_api_key_configured: boolean
  alert_webhook_url: string
  alert_webhook_secret_configured: boolean
  alert_delivery_min_severity: 'info' | 'warning' | 'critical'
  sms_http_endpoint: string
  sms_http_from: string
  sms_http_auth_header: string
  sms_http_auth_scheme: string
  sms_http_delivery_callback_url: string
  sms_http_auth_token_configured: boolean
  voice_http_endpoint: string
  voice_http_from: string
  voice_http_auth_header: string
  voice_http_auth_scheme: string
  voice_http_status_callback_url: string
  voice_http_auth_token_configured: boolean
  whatsapp_cloud_api_base_url: string
  whatsapp_phone_number_id: string
  whatsapp_preview_urls: boolean
  whatsapp_access_token_configured: boolean
  facebook_graph_api_base_url: string
  facebook_page_id: string
  facebook_messaging_type: string
  facebook_page_access_token_configured: boolean
  instagram_graph_api_base_url: string
  instagram_business_account_id: string
  instagram_access_token_configured: boolean
  updated_at: string
}

export interface BackendUpdateIntegrationCredentialSettingsInput {
  ai_provider?: string
  anthropic_api_key?: string
  anthropic_api_base_url?: string
  anthropic_model?: string
  clear_anthropic_api_key?: boolean
  alert_webhook_url?: string
  alert_webhook_secret?: string
  alert_delivery_min_severity?: 'info' | 'warning' | 'critical'
  clear_alert_webhook_secret?: boolean
  sms_http_endpoint?: string
  sms_http_auth_token?: string
  sms_http_from?: string
  sms_http_auth_header?: string
  sms_http_auth_scheme?: string
  sms_http_delivery_callback_url?: string
  clear_sms_http_auth_token?: boolean
  voice_http_endpoint?: string
  voice_http_auth_token?: string
  voice_http_from?: string
  voice_http_auth_header?: string
  voice_http_auth_scheme?: string
  voice_http_status_callback_url?: string
  clear_voice_http_auth_token?: boolean
  whatsapp_cloud_api_base_url?: string
  whatsapp_phone_number_id?: string
  whatsapp_access_token?: string
  whatsapp_preview_urls?: boolean
  clear_whatsapp_access_token?: boolean
  facebook_graph_api_base_url?: string
  facebook_page_id?: string
  facebook_page_access_token?: string
  facebook_messaging_type?: string
  clear_facebook_page_access_token?: boolean
  instagram_graph_api_base_url?: string
  instagram_business_account_id?: string
  instagram_access_token?: string
  clear_instagram_access_token?: boolean
}

export interface BackendTrackerSummary {
  market_id: string
  market: string
  epics: string[]
  current_status: string
  known_dependencies: string[]
}

export interface BackendSnapshot {
  health: BackendHealth
  session: BackendAuthContext
  users: BackendUser[]
  settings: BackendSettings
  tracker: BackendTrackerSummary
  analytics: BackendAnalyticsSummary
  analyticsRollups: BackendAnalyticsRollup[]
  csatFeedback: BackendCsatFeedback[]
  providers: BackendConnectorProvider[]
  connectorAccounts: BackendConnectorAccount[]
  outboundMessages: BackendOutboundMessage[]
  outboundProviderConfig: BackendOutboundProviderConfig[]
  inboundProviderConfig: BackendInboundProviderConfig[]
  attachmentProviderConfig: BackendAttachmentProviderConfig | null
  emailProviderSettings: BackendEmailProviderSettings | null
  integrationCredentialSettings: BackendIntegrationCredentialSettings | null
  operationalAlerts: BackendOperationalAlert[]
  alertDeliveries: BackendOperationalAlertDelivery[]
  alertDeliveryConfig: BackendOperationalAlertDeliveryConfig
  supervisorRecommendations: BackendSupervisorRecommendation[]
  channels: BackendChannel[]
  ticketFields: BackendTicketField[]
  agents: BackendAgent[]
  supportGroups: BackendSupportGroup[]
  slaPolicies: BackendSlaPolicy[]
  businessHours: BackendBusinessHours[]
  ticketTemplates: BackendTicketTemplate[]
  tags: BackendTag[]
  csatSurveys: BackendCsatSurvey[]
  companies: BackendCompany[]
  customers: BackendCustomer[]
  tickets: BackendTicketContext[]
  handoffs: BackendHandoff[]
  connector_accounts: BackendConnectorAccount[]
  outbound_messages: BackendOutboundMessage[]
  outbound_provider_config: BackendOutboundProviderConfig[]
  inbound_provider_config: BackendInboundProviderConfig[]
  attachment_provider_config: BackendAttachmentProviderConfig | null
  email_provider_settings: BackendEmailProviderSettings | null
  integration_credential_settings: BackendIntegrationCredentialSettings | null
  operational_alerts: BackendOperationalAlert[]
  alert_deliveries: BackendOperationalAlertDelivery[]
  alert_delivery_config: BackendOperationalAlertDeliveryConfig
  supervisor_recommendations: BackendSupervisorRecommendation[]
  analytics_rollups: BackendAnalyticsRollup[]
  csat_feedback: BackendCsatFeedback[]
  ticket_fields: BackendTicketField[]
  support_groups: BackendSupportGroup[]
  sla_policies: BackendSlaPolicy[]
  business_hours: BackendBusinessHours[]
  ticket_templates: BackendTicketTemplate[]
  csat_surveys: BackendCsatSurvey[]
  knowledge: BackendKnowledgeArticle[]
  macros: BackendResponseMacro[]
  rules: BackendAutomationRule[]
}

export interface BackendSyncState {
  status: 'idle' | 'syncing' | 'connected' | 'error'
  baseUrl: string
  lastSyncAt?: string
  error?: string
  snapshot?: BackendSnapshot
  oidcProviderConfig?: BackendOidcProviderConfig
}

export interface BackendMarket {
  id: string
  code: string
  name: string
  timezone: string
  currency: string
  default_locale: string
  support_email: string
  whatsapp_number?: string | null
  facebook_page?: string | null
  instagram_handle?: string | null
}

export type BackendPermission =
  | 'operations.write'
  | 'supervisor.control'
  | 'audit.read'
  | 'setup.manage'

export type BackendPermissionProfile =
  | 'role_default'
  | 'read_only'
  | 'operations'
  | 'supervisor'
  | 'admin'
  | 'custom'

export interface BackendPermissionOverrides {
  allow: BackendPermission[]
  deny: BackendPermission[]
}

export interface BackendUser {
  id: string
  name: string
  email: string
  role: 'agent' | 'supervisor' | 'admin' | 'auditor' | 'service_account'
  market_ids: string[]
  default_market_id: string
  active: boolean
  password_reset_required: boolean
  mfa_enabled: boolean
  mfa_confirmed_at?: string | null
  mfa_last_verified_at?: string | null
  permission_profile: BackendPermissionProfile
  permission_overrides: BackendPermissionOverrides
  effective_permissions: BackendPermission[]
  external_identity_provider?: string | null
  external_subject?: string | null
  external_last_login_at?: string | null
  last_login_at?: string | null
}

export interface BackendAuthContext {
  user: BackendUser
  market: BackendMarket
}

export interface BackendSession extends BackendAuthContext {
  access_token: string
  token_type: string
  available_markets: BackendMarket[]
}

export interface BackendLoginInput {
  email: string
  password: string
  market_id?: string
  mfa_code?: string
}

export interface BackendOidcProviderConfig {
  provider_name: string
  enabled: boolean
  configured: boolean
  login_available: boolean
  authorization_endpoint_configured: boolean
  token_endpoint_configured: boolean
  userinfo_endpoint_configured: boolean
  redirect_url_configured: boolean
  client_configured: boolean
  auto_provision_enabled: boolean
  default_role: BackendUser['role']
  default_market_id?: string | null
  allowed_email_domains: string[]
  required_settings: string[]
  missing_settings: string[]
  notes: string
}

export interface BackendOidcStartInput {
  market_id: string
  return_to?: string
}

export interface BackendOidcStartResponse {
  authorization_url: string
  state: string
  expires_at: string
}

export interface BackendOidcCallbackInput {
  code: string
  state: string
}

export interface BackendMfaEnrollment {
  secret: string
  otpauth_uri: string
  issuer: string
  digits: number
  period_seconds: number
}

export interface BackendConfirmMfaInput {
  code: string
}

export interface BackendDisableMfaInput {
  current_password: string
  code?: string
}

export interface BackendChannel {
  id: string
  market_id: string
  type: string
  name: string
  handle: string
  health: 'healthy' | 'degraded' | 'paused'
  queued: number
  active: number
  sla_risk: number
  capabilities: string[]
}

export type BackendTicketFieldType =
  | 'text'
  | 'textarea'
  | 'select'
  | 'multiselect'
  | 'checkbox'
  | 'number'
  | 'date'

export interface BackendTicketField {
  id: string
  market_id: string
  key: string
  label: string
  field_type: BackendTicketFieldType
  required: boolean
  active: boolean
  system: boolean
  options: string[]
  channels: string[]
  placeholder: string
  help_text: string
  position: number
  updated_at: string
}

export interface BackendPortalAnswerSuggestion {
  article_id: string
  title: string
  body: string
  language: string
  tags: string[]
  score: number
  reasons: string[]
  matched_terms: string[]
  updated_at: string
}

export interface BackendPortalAnswersResponse {
  market_id: string
  market_code: string
  query: string
  suggestions: BackendPortalAnswerSuggestion[]
  ticket_fields: BackendTicketField[]
}

export interface BackendCreatePortalTicketInput {
  name: string
  email: string
  phone?: string
  subject: string
  description: string
  priority?: 'low' | 'normal' | 'high' | 'urgent'
  custom_fields?: Record<string, unknown>
  search_query?: string
}

export interface BackendPortalTicketResponse {
  ticket_id: string
  public_id: string
  status: BackendTicket['status']
  priority: BackendTicket['priority']
  created_at: string
  article_suggestions: BackendPortalAnswerSuggestion[]
}

export interface BackendPortalTicketTimelineEvent {
  id: string
  type: string
  channel: string
  actor: string
  body: string
  created_at: string
}

export interface BackendPortalAttachment {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  scan_status: 'pending' | 'clean' | 'blocked' | 'failed'
  lifecycle_status: 'active' | 'deleted' | 'purged'
  created_at: string
}

export interface BackendPortalTicketDetail {
  ticket_id: string
  public_id: string
  subject: string
  description: string
  status: BackendTicket['status']
  customer_status: string
  priority: BackendTicket['priority']
  created_at: string
  updated_at: string
  next_step: string
  reply_allowed: boolean
  timeline: BackendPortalTicketTimelineEvent[]
  attachments: BackendPortalAttachment[]
  article_suggestions: BackendPortalAnswerSuggestion[]
}

export interface BackendPortalTicketReplyInput {
  email: string
  body: string
}

export interface BackendAgent {
  id: string
  market_ids: string[]
  name: string
  email: string
  team: string
  status: 'available' | 'busy' | 'away' | 'offline'
  occupancy: number
  capacity: number
  skills: string[]
  languages: string[]
}

export interface BackendSupportGroup {
  id: string
  market_id: string
  name: string
  description: string
  team_email: string | null
  active: boolean
  channels: string[]
  skills: string[]
  member_count: number
  open_ticket_count: number
  sla_risk_count: number
  created_at: string
  updated_at: string
}

export interface BackendGlobalSearchResult {
  id: string
  type: 'ticket' | 'customer' | 'company' | 'knowledge' | 'support_group' | 'handoff' | 'agent'
  title: string
  subtitle: string
  description: string
  score: number
  screen: string | null
  entity_id: string
  metadata: Record<string, unknown>
}

export interface BackendCreateSupportGroupInput {
  name: string
  description?: string
  team_email?: string | null
  active?: boolean
  channels?: string[]
  skills?: string[]
}

export interface BackendUpdateSupportGroupInput {
  name?: string
  description?: string
  team_email?: string | null
  active?: boolean
  channels?: string[]
  skills?: string[]
}

export interface BackendSlaPolicy {
  id: string
  market_id: string
  name: string
  active: boolean
  channels: string[]
  priority: 'low' | 'normal' | 'high' | 'urgent'
  first_response_minutes: number
  resolution_minutes: number
  business_hours: string
  position: number
  created_at: string
  updated_at: string
}

export interface BackendCreateSlaPolicyInput {
  name: string
  active?: boolean
  channels?: string[]
  priority?: BackendSlaPolicy['priority']
  first_response_minutes?: number
  resolution_minutes?: number
  business_hours?: string
  position?: number
}

export interface BackendUpdateSlaPolicyInput {
  name?: string
  active?: boolean
  channels?: string[]
  priority?: BackendSlaPolicy['priority']
  first_response_minutes?: number
  resolution_minutes?: number
  business_hours?: string
  position?: number
}

export interface BackendBusinessHoursDay {
  day: string
  enabled: boolean
  open: string
  close: string
}

export interface BackendBusinessHours {
  id: string
  market_id: string
  name: string
  timezone: string
  active: boolean
  days: BackendBusinessHoursDay[]
  created_at: string
  updated_at: string
}

export interface BackendCreateBusinessHoursInput {
  name: string
  timezone?: string
  active?: boolean
  days?: BackendBusinessHoursDay[]
}

export interface BackendUpdateBusinessHoursInput {
  name?: string
  timezone?: string
  active?: boolean
  days?: BackendBusinessHoursDay[]
}

export interface BackendTicketTemplate {
  id: string
  market_id: string
  name: string
  subject: string
  description: string
  priority: 'low' | 'normal' | 'high' | 'urgent'
  channel: string
  group: string
  tags: string[]
  active: boolean
  created_at: string
  updated_at: string
}

export interface BackendCreateTicketTemplateInput {
  name: string
  subject: string
  description?: string
  priority?: BackendTicketTemplate['priority']
  channel?: string
  group?: string
  tags?: string[]
  active?: boolean
}

export interface BackendUpdateTicketTemplateInput {
  name?: string
  subject?: string
  description?: string
  priority?: BackendTicketTemplate['priority']
  channel?: string
  group?: string
  tags?: string[]
  active?: boolean
}

export interface BackendTag {
  id: string
  market_id: string
  name: string
  color: string
  description: string
  active: boolean
  created_at: string
  updated_at: string
}

export interface BackendCreateTagInput {
  name: string
  color?: string
  description?: string
  active?: boolean
}

export interface BackendUpdateTagInput {
  name?: string
  color?: string
  description?: string
  active?: boolean
}

export interface BackendCsatSurvey {
  id: string
  market_id: string
  name: string
  question: string
  scale: number
  channels: string[]
  active: boolean
  created_at: string
  updated_at: string
}

export interface BackendCreateCsatSurveyInput {
  name: string
  question: string
  scale?: number
  channels?: string[]
  active?: boolean
}

export interface BackendUpdateCsatSurveyInput {
  name?: string
  question?: string
  scale?: number
  channels?: string[]
  active?: boolean
}

export interface BackendCompany {
  id: string
  market_id: string
  name: string
  tier: string
  health_score: number
  account_value: number
}

export interface BackendContactPoint {
  channel: string
  value: string
  verified: boolean
}

export interface BackendCustomer {
  id: string
  market_id: string
  name: string
  email: string
  company_id: string | null
  location: string
  sentiment: 'positive' | 'neutral' | 'frustrated' | 'angry'
  preferred_channels: string[]
  contact_points: BackendContactPoint[]
  tags: string[]
  notes: string
}

export interface BackendTicketTask {
  id: string
  label: string
  complete: boolean
}

export interface BackendSla {
  first_response_due_at: string
  resolution_due_at: string
  risk: 'on_track' | 'at_risk' | 'breached'
  breached: boolean
}

export interface BackendTimelineEvent {
  id: string
  ticket_id: string
  type: string
  channel: string
  actor: string
  body: string
  created_at: string
  public: boolean
  metadata: Record<string, unknown>
}

export interface BackendAiDecision {
  id: string
  ticket_id: string
  created_at: string
  decision_type: string
  confidence: number
  summary: string
  model_version: string
  input_reference: string
  override_allowed: boolean
}

export interface BackendAttachment {
  id: string
  market_id: string
  ticket_id: string
  timeline_event_id: string | null
  filename: string
  content_type: string
  size_bytes: number
  storage_key: string
  uploaded_by: string
  scan_status: 'pending' | 'clean' | 'blocked' | 'failed'
  scan_result: string | null
  lifecycle_status: 'active' | 'deleted' | 'purged'
  retained_until: string | null
  deleted_at: string | null
  deleted_by: string | null
  deletion_reason: string | null
  purged_at: string | null
  created_at: string
  updated_at: string
}

export interface BackendAttachmentRetentionPolicy {
  market_id: string
  active_retention_days: number
  deleted_retention_days: number
  active_cutoff_at: string
  deleted_cutoff_at: string
  prune_limit: number
  active_attachments: number
  deleted_attachments: number
  purged_attachments: number
  purgeable_attachments: number
}

export interface BackendAttachmentRetentionResult {
  policy: BackendAttachmentRetentionPolicy
  purged_attachments: number
  attachment_ids: string[]
  audit_event_id: string | null
}

export interface BackendTicket {
  id: string
  market_id: string
  public_id: string
  subject: string
  description: string
  customer_id: string
  channel: string
  status: 'open' | 'pending' | 'waiting' | 'solved' | 'closed'
  priority: 'low' | 'normal' | 'high' | 'urgent'
  sentiment: 'positive' | 'neutral' | 'frustrated' | 'angry'
  assignee_id: string | null
  team: string
  tags: string[]
  custom_fields: Record<string, unknown>
  tasks: BackendTicketTask[]
  sla: BackendSla
  ai_summary: string
  recommended_action: string
  created_at: string
  updated_at: string
}

export interface BackendTicketContext {
  ticket: BackendTicket
  customer: BackendCustomer
  company: BackendCompany | null
  assignee: BackendAgent | null
  timeline: BackendTimelineEvent[]
  handoffs: BackendHandoff[]
  ai_decisions: BackendAiDecision[]
  outbound_messages: BackendOutboundMessage[]
  attachments: BackendAttachment[]
  csat_feedback: BackendCsatFeedback[]
  knowledge_suggestions?: BackendKnowledgeSuggestion[]
  macro_suggestions?: BackendResponseMacroSuggestion[]
  duplicate_suggestions?: BackendDuplicateTicketSuggestion[]
}

export interface BackendHandoff {
  id: string
  market_id: string
  ticket_id: string
  linked_ticket_id: string | null
  from_team: string
  to_team: string
  requested_by: string
  reason: string
  status: 'requested' | 'accepted' | 'blocked' | 'resolved' | 'cancelled'
  due_at: string
  checklist: BackendTicketTask[]
  blocker: string | null
  created_at: string
  updated_at: string
}

export interface BackendKnowledgeArticle {
  id: string
  market_ids: string[]
  title: string
  status: string
  language: string
  channels: string[]
  tags: string[]
  body: string
  updated_at: string
}

export interface BackendKnowledgeSuggestion {
  article: BackendKnowledgeArticle
  score: number
  reasons: string[]
  matched_terms: string[]
}

export interface BackendResponseMacro {
  id: string
  market_id: string
  name: string
  body: string
  language: string
  channels: string[]
  tags: string[]
  shortcut: string | null
  active: boolean
  usage_count: number
  last_used_at: string | null
  updated_at: string
}

export interface BackendCreateResponseMacroInput {
  name: string
  body: string
  language?: string
  channels?: string[]
  tags?: string[]
  shortcut?: string | null
  active?: boolean
}

export interface BackendUpdateResponseMacroInput {
  name?: string
  body?: string
  language?: string
  channels?: string[]
  tags?: string[]
  shortcut?: string | null
  active?: boolean
}

export interface BackendResponseMacroSuggestion {
  macro: BackendResponseMacro
  score: number
  reasons: string[]
  matched_terms: string[]
}

export interface BackendDuplicateTicketSuggestion {
  ticket: BackendTicket
  customer: BackendCustomer | null
  score: number
  reasons: string[]
  matched_terms: string[]
}

export interface BackendMergeTicketsInput {
  source_ticket_id: string
  reason: string
  actor?: string
  close_source?: boolean
}

export interface BackendMergeTicketsResponse {
  target_ticket: BackendTicket
  source_ticket: BackendTicket
  target_timeline_event: BackendTimelineEvent
  source_timeline_event: BackendTimelineEvent
  audit_event_id: string | null
}

export interface BackendAutomationRule {
  id: string
  market_id: string
  name: string
  enabled: boolean
  trigger: string
  action: string
  last_fired_at: string | null
  failure_count: number
}

export interface BackendCreateTicketInput {
  subject: string
  description: string
  customer_id: string
  channel: string
  priority?: BackendTicket['priority']
  tags?: string[]
  custom_fields?: Record<string, unknown>
}

export interface BackendUpdateTicketInput {
  status?: BackendTicket['status']
  priority?: BackendTicket['priority']
  assignee_id?: string | null
  tags?: string[]
  custom_fields?: Record<string, unknown>
}

export interface BackendCreateTicketFieldInput {
  key: string
  label: string
  field_type: BackendTicketFieldType
  required?: boolean
  active?: boolean
  options?: string[]
  channels?: string[]
  placeholder?: string
  help_text?: string
  position?: number
}

export type BackendUpdateTicketFieldInput = Partial<
  Omit<BackendCreateTicketFieldInput, 'key'>
>

export interface BackendReplyInput {
  channel: string
  actor: string
  body: string
  public: boolean
  idempotency_key?: string
}

export interface BackendCreateAttachmentInput {
  filename: string
  content_type: string
  size_bytes: number
  storage_key?: string
}

export interface BackendCreateHandoffInput {
  to_team: string
  requested_by: string
  reason: string
  due_minutes: number
  checklist: string[]
}

export interface BackendUpdateHandoffInput {
  status?: BackendHandoff['status']
  blocker?: string | null
  checklist_item_id?: string
  checklist_item_complete?: boolean
}

export interface BackendUpdateChannelInput {
  health?: BackendChannel['health']
  queued?: number
  active?: number
  sla_risk?: number
}

export interface BackendUpdateKnowledgeInput {
  status?: BackendKnowledgeArticle['status']
}

export interface BackendUpdateRuleInput {
  enabled?: boolean
}

export interface BackendUpdateOperationalAlertInput {
  status: BackendOperationalAlertStatus
  note?: string
}

export interface BackendCreateUserInput {
  name: string
  email: string
  temporary_password: string
  role: BackendUser['role']
  market_ids: string[]
  default_market_id?: string
  active?: boolean
  permission_profile?: BackendPermissionProfile
  permission_overrides?: BackendPermissionOverrides
}

export interface BackendUpdateUserInput {
  name?: string
  email?: string
  temporary_password?: string
  role?: BackendUser['role']
  market_ids?: string[]
  default_market_id?: string
  active?: boolean
  permission_profile?: BackendPermissionProfile
  permission_overrides?: BackendPermissionOverrides
}

export interface BackendChangePasswordInput {
  current_password: string
  new_password: string
}

interface BackendFrontendSnapshot {
  session: BackendAuthContext
  users: BackendUser[]
  settings: BackendSettings
  channels: BackendChannel[]
  ticket_fields: BackendTicketField[]
  agents: BackendAgent[]
  support_groups: BackendSupportGroup[]
  sla_policies: BackendSlaPolicy[]
  business_hours: BackendBusinessHours[]
  ticket_templates: BackendTicketTemplate[]
  tags: BackendTag[]
  csat_surveys: BackendCsatSurvey[]
  companies: BackendCompany[]
  customers: BackendCustomer[]
  tickets: BackendTicketContext[]
  handoffs: BackendHandoff[]
  connector_accounts: BackendConnectorAccount[]
  knowledge: BackendKnowledgeArticle[]
  macros: BackendResponseMacro[]
  rules: BackendAutomationRule[]
  outbound_messages: BackendOutboundMessage[]
  outbound_provider_config: BackendOutboundProviderConfig[]
  inbound_provider_config: BackendInboundProviderConfig[]
  attachment_provider_config: BackendAttachmentProviderConfig | null
  email_provider_settings: BackendEmailProviderSettings | null
  integration_credential_settings: BackendIntegrationCredentialSettings | null
  operational_alerts: BackendOperationalAlert[]
  alert_deliveries: BackendOperationalAlertDelivery[]
  alert_delivery_config: BackendOperationalAlertDeliveryConfig
  supervisor_recommendations: BackendSupervisorRecommendation[]
  analytics: BackendAnalyticsSummary
  analytics_rollups: BackendAnalyticsRollup[]
  csat_feedback: BackendCsatFeedback[]
  tracker: BackendTrackerSummary
}

function trimTrailingSlash(value: string) {
  return value.endsWith('/') ? value.slice(0, -1) : value
}

export function getBackendBaseUrl() {
  const configured = import.meta.env.VITE_OMNI_API_BASE_URL
  if (configured) return trimTrailingSlash(configured)

  if (typeof window !== 'undefined') {
    const { hostname, origin } = window.location
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'
    if (!isLocalhost) return `${trimTrailingSlash(origin)}/api/v1`
  }

  return 'http://127.0.0.1:8000/api/v1'
}

function authHeaders(session?: BackendSession | null) {
  if (!session) return {}
  return {
    Authorization: `Bearer ${session.access_token}`,
    'X-Omni-Market': session.market.id,
  }
}

function appendDefinedQuery(params: URLSearchParams, key: string, value: string | number | undefined) {
  if (value === undefined || value === '') return
  params.set(key, String(value))
}

function contentDispositionFilename(header: string | null) {
  if (!header) return undefined
  const match = /filename="?([^";]+)"?/i.exec(header)
  return match?.[1]
}

async function fetchJson<T>(
  path: string,
  init?: RequestInit,
  session?: BackendSession | null,
): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  Object.entries(authHeaders(session)).forEach(([key, value]) => headers.set(key, value))

  const response = await fetch(`${getBackendBaseUrl()}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`.trim()
    try {
      const errorBody = (await response.json()) as { detail?: string }
      if (errorBody.detail) {
        message = errorBody.detail
      }
    } catch {
      // Keep the HTTP status when the server does not return a JSON problem body.
    }
    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

async function fetchAuthenticatedText(path: string, session: BackendSession): Promise<BackendAuditExport> {
  const headers = new Headers()
  Object.entries(authHeaders(session)).forEach(([key, value]) => headers.set(key, value))

  const response = await fetch(`${getBackendBaseUrl()}${path}`, { headers })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`.trim()
    try {
      const errorBody = (await response.json()) as { detail?: string }
      if (errorBody.detail) message = errorBody.detail
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new Error(message)
  }

  return {
    content: await response.text(),
    contentType: response.headers.get('Content-Type') ?? 'text/plain',
    filename: contentDispositionFilename(response.headers.get('Content-Disposition')) ?? 'omni-audit-export.txt',
  }
}

export async function loginBackend(input: BackendLoginInput): Promise<BackendSession> {
  return fetchJson<BackendSession>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function fetchOidcProviderConfig(): Promise<BackendOidcProviderConfig> {
  return fetchJson<BackendOidcProviderConfig>('/auth/oidc/config')
}

export async function startOidcLoginBackend(input: BackendOidcStartInput): Promise<BackendOidcStartResponse> {
  const params = new URLSearchParams()
  appendDefinedQuery(params, 'market_id', input.market_id)
  appendDefinedQuery(params, 'return_to', input.return_to)
  return fetchJson<BackendOidcStartResponse>(`/auth/oidc/start?${params.toString()}`)
}

export async function completeOidcLoginBackend(
  input: BackendOidcCallbackInput,
): Promise<BackendSession> {
  return fetchJson<BackendSession>('/auth/oidc/callback', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function fetchBackendSnapshot(
  session: BackendSession,
  signal?: AbortSignal,
): Promise<BackendSnapshot> {
  const [health, providers, frontendSnapshot] = await Promise.all([
    fetchJson<BackendHealth>('/health', { signal }),
    fetchJson<BackendConnectorProvider[]>('/connectors/providers', { signal }, session),
    fetchJson<BackendFrontendSnapshot>('/frontend/snapshot', { signal }, session),
  ])

  return {
    health,
    providers,
    ticketFields: frontendSnapshot.ticket_fields ?? [],
    supportGroups: frontendSnapshot.support_groups ?? [],
    slaPolicies: frontendSnapshot.sla_policies ?? [],
    businessHours: frontendSnapshot.business_hours ?? [],
    ticketTemplates: frontendSnapshot.ticket_templates ?? [],
    csatSurveys: frontendSnapshot.csat_surveys ?? [],
    connectorAccounts: frontendSnapshot.connector_accounts,
    outboundMessages: frontendSnapshot.outbound_messages,
    outboundProviderConfig: frontendSnapshot.outbound_provider_config ?? [],
    inboundProviderConfig: frontendSnapshot.inbound_provider_config ?? [],
    attachmentProviderConfig: frontendSnapshot.attachment_provider_config ?? null,
    emailProviderSettings: frontendSnapshot.email_provider_settings ?? null,
    integrationCredentialSettings: frontendSnapshot.integration_credential_settings ?? null,
    operationalAlerts: frontendSnapshot.operational_alerts,
    alertDeliveries: frontendSnapshot.alert_deliveries,
    alertDeliveryConfig: frontendSnapshot.alert_delivery_config,
    supervisorRecommendations: frontendSnapshot.supervisor_recommendations ?? [],
    analyticsRollups: frontendSnapshot.analytics_rollups ?? [],
    csatFeedback: frontendSnapshot.csat_feedback ?? [],
    ...frontendSnapshot,
  }
}

export async function fetchBackendGlobalSearch(
  query: string,
  session: BackendSession,
  limit = 10,
  signal?: AbortSignal,
): Promise<BackendGlobalSearchResult[]> {
  const params = new URLSearchParams()
  appendDefinedQuery(params, 'q', query)
  appendDefinedQuery(params, 'limit', limit)
  return fetchJson<BackendGlobalSearchResult[]>(`/search?${params.toString()}`, { signal }, session)
}

export async function patchBackendSettings(
  patch: Partial<BackendSettings>,
  session: BackendSession,
): Promise<BackendSettings> {
  return fetchJson<BackendSettings>('/settings', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }, session)
}

export async function patchBackendEmailSettings(
  patch: BackendUpdateEmailProviderSettingsInput,
  session: BackendSession,
): Promise<BackendEmailProviderSettings> {
  return fetchJson<BackendEmailProviderSettings>('/email/settings', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }, session)
}

export async function patchBackendIntegrationCredentialSettings(
  patch: BackendUpdateIntegrationCredentialSettingsInput,
  session: BackendSession,
): Promise<BackendIntegrationCredentialSettings> {
  return fetchJson<BackendIntegrationCredentialSettings>('/integration-credentials/settings', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }, session)
}

export async function fetchBackendProductionAccountRequests(
  session: BackendSession,
): Promise<BackendProductionAccountRequestPack> {
  return fetchJson<BackendProductionAccountRequestPack>('/production/account-requests', undefined, session)
}

export async function sendBackendProductionAccountRequestEmail(
  session: BackendSession,
): Promise<BackendProductionAccountRequestDelivery> {
  return fetchJson<BackendProductionAccountRequestDelivery>('/production/account-requests/email', {
    method: 'POST',
  }, session)
}

export async function fetchBackendProductionReadinessChecklist(
  session: BackendSession,
): Promise<BackendProductionReadinessChecklist> {
  return fetchJson<BackendProductionReadinessChecklist>('/production/readiness-checklist', undefined, session)
}

export async function fetchBackendProductionAccountReferences(
  session: BackendSession,
): Promise<BackendProductionAccountReference[]> {
  return fetchJson<BackendProductionAccountReference[]>('/production/account-references', undefined, session)
}

export async function createBackendProductionAccountReference(
  input: BackendCreateProductionAccountReferenceInput,
  session: BackendSession,
): Promise<BackendProductionAccountReference> {
  return fetchJson<BackendProductionAccountReference>('/production/account-references', {
    method: 'POST',
    body: JSON.stringify(input),
  }, session)
}

export async function patchBackendProductionAccountReference(
  referenceId: string,
  input: BackendUpdateProductionAccountReferenceInput,
  session: BackendSession,
): Promise<BackendProductionAccountReference> {
  return fetchJson<BackendProductionAccountReference>(`/production/account-references/${referenceId}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  }, session)
}

export async function fetchBackendProductionAccountReferenceDocs(
  session: BackendSession,
): Promise<BackendProductionAccountReferenceDocs> {
  return fetchJson<BackendProductionAccountReferenceDocs>('/production/account-references/docs', undefined, session)
}

export async function fetchBackendAuditRetentionPolicy(
  session: BackendSession,
): Promise<BackendAuditRetentionPolicy> {
  return fetchJson<BackendAuditRetentionPolicy>('/audit/retention', undefined, session)
}

export async function pruneBackendAuditRetention(
  session: BackendSession,
): Promise<BackendAuditRetentionResult> {
  return fetchJson<BackendAuditRetentionResult>(
    '/audit/retention/prune',
    {
      method: 'POST',
    },
    session,
  )
}

export async function fetchBackendAttachmentRetentionPolicy(
  session: BackendSession,
): Promise<BackendAttachmentRetentionPolicy> {
  return fetchJson<BackendAttachmentRetentionPolicy>('/attachments/retention', undefined, session)
}

export async function pruneBackendAttachmentRetention(
  session: BackendSession,
): Promise<BackendAttachmentRetentionResult> {
  return fetchJson<BackendAttachmentRetentionResult>(
    '/attachments/retention/prune',
    {
      method: 'POST',
    },
    session,
  )
}

export async function exportBackendAudit(
  options: BackendAuditExportOptions,
  session: BackendSession,
): Promise<BackendAuditExport> {
  const params = new URLSearchParams()
  params.set('format', options.format)
  appendDefinedQuery(params, 'actor', options.actor)
  appendDefinedQuery(params, 'action', options.action)
  appendDefinedQuery(params, 'entity_type', options.entity_type)
  appendDefinedQuery(params, 'entity_id', options.entity_id)
  appendDefinedQuery(params, 'since', options.since)
  appendDefinedQuery(params, 'until', options.until)
  appendDefinedQuery(params, 'limit', options.limit)

  const exportPayload = await fetchAuthenticatedText(`/audit/export?${params.toString()}`, session)
  if (options.format === 'json' && exportPayload.filename === 'omni-audit-export.txt') {
    return { ...exportPayload, filename: 'omni-audit-export.json' }
  }
  if (options.format === 'csv' && exportPayload.filename === 'omni-audit-export.txt') {
    return { ...exportPayload, filename: 'omni-audit-export.csv' }
  }
  return exportPayload
}

export async function createBackendUser(
  input: BackendCreateUserInput,
  session: BackendSession,
): Promise<BackendUser> {
  return fetchJson<BackendUser>(
    '/auth/users',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendUser(
  userId: string,
  patch: BackendUpdateUserInput,
  session: BackendSession,
): Promise<BackendUser> {
  return fetchJson<BackendUser>(
    `/auth/users/${userId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function createBackendSupportGroup(
  input: BackendCreateSupportGroupInput,
  session: BackendSession,
): Promise<BackendSupportGroup> {
  return fetchJson<BackendSupportGroup>(
    '/support-groups',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendSupportGroup(
  groupId: string,
  patch: BackendUpdateSupportGroupInput,
  session: BackendSession,
): Promise<BackendSupportGroup> {
  return fetchJson<BackendSupportGroup>(
    `/support-groups/${groupId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function createBackendSlaPolicy(
  input: BackendCreateSlaPolicyInput,
  session: BackendSession,
): Promise<BackendSlaPolicy> {
  return fetchJson<BackendSlaPolicy>(
    '/sla-policies',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendSlaPolicy(
  policyId: string,
  patch: BackendUpdateSlaPolicyInput,
  session: BackendSession,
): Promise<BackendSlaPolicy> {
  return fetchJson<BackendSlaPolicy>(
    `/sla-policies/${policyId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function createBackendBusinessHours(
  input: BackendCreateBusinessHoursInput,
  session: BackendSession,
): Promise<BackendBusinessHours> {
  return fetchJson<BackendBusinessHours>(
    '/business-hours',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendBusinessHours(
  businessHoursId: string,
  patch: BackendUpdateBusinessHoursInput,
  session: BackendSession,
): Promise<BackendBusinessHours> {
  return fetchJson<BackendBusinessHours>(
    `/business-hours/${businessHoursId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function createBackendTicketTemplate(
  input: BackendCreateTicketTemplateInput,
  session: BackendSession,
): Promise<BackendTicketTemplate> {
  return fetchJson<BackendTicketTemplate>(
    '/ticket-templates',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendTicketTemplate(
  templateId: string,
  patch: BackendUpdateTicketTemplateInput,
  session: BackendSession,
): Promise<BackendTicketTemplate> {
  return fetchJson<BackendTicketTemplate>(
    `/ticket-templates/${templateId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function createBackendTag(
  input: BackendCreateTagInput,
  session: BackendSession,
): Promise<BackendTag> {
  return fetchJson<BackendTag>(
    '/tags',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendTag(
  tagId: string,
  patch: BackendUpdateTagInput,
  session: BackendSession,
): Promise<BackendTag> {
  return fetchJson<BackendTag>(
    `/tags/${tagId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function createBackendCsatSurvey(
  input: BackendCreateCsatSurveyInput,
  session: BackendSession,
): Promise<BackendCsatSurvey> {
  return fetchJson<BackendCsatSurvey>(
    '/csat-surveys',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendCsatSurvey(
  surveyId: string,
  patch: BackendUpdateCsatSurveyInput,
  session: BackendSession,
): Promise<BackendCsatSurvey> {
  return fetchJson<BackendCsatSurvey>(
    `/csat-surveys/${surveyId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function changeBackendPassword(
  input: BackendChangePasswordInput,
  session: BackendSession,
): Promise<void> {
  return fetchJson<void>(
    '/auth/password',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function enrollBackendMfa(session: BackendSession): Promise<BackendMfaEnrollment> {
  return fetchJson<BackendMfaEnrollment>(
    '/auth/mfa/enroll',
    {
      method: 'POST',
    },
    session,
  )
}

export async function confirmBackendMfa(
  input: BackendConfirmMfaInput,
  session: BackendSession,
): Promise<BackendUser> {
  return fetchJson<BackendUser>(
    '/auth/mfa/confirm',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function disableBackendMfa(
  input: BackendDisableMfaInput,
  session: BackendSession,
): Promise<BackendUser> {
  return fetchJson<BackendUser>(
    '/auth/mfa/disable',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function createBackendTicket(
  input: BackendCreateTicketInput,
  session: BackendSession,
): Promise<BackendTicket> {
  return fetchJson<BackendTicket>(
    '/tickets',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function fetchBackendPortalAnswers(
  marketCode: string,
  query: string,
  limit = 5,
): Promise<BackendPortalAnswersResponse> {
  const params = new URLSearchParams()
  appendDefinedQuery(params, 'q', query)
  appendDefinedQuery(params, 'limit', Math.max(1, Math.min(10, limit)))
  return fetchJson<BackendPortalAnswersResponse>(
    `/portal/${encodeURIComponent(marketCode.toLowerCase())}/answers?${params.toString()}`,
  )
}

export async function createBackendPortalTicket(
  marketCode: string,
  input: BackendCreatePortalTicketInput,
): Promise<BackendPortalTicketResponse> {
  return fetchJson<BackendPortalTicketResponse>(
    `/portal/${encodeURIComponent(marketCode.toLowerCase())}/tickets`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export async function fetchBackendPortalTicket(
  marketCode: string,
  publicId: string,
  email: string,
): Promise<BackendPortalTicketDetail> {
  const params = new URLSearchParams()
  appendDefinedQuery(params, 'email', email)
  return fetchJson<BackendPortalTicketDetail>(
    `/portal/${encodeURIComponent(marketCode.toLowerCase())}/tickets/${encodeURIComponent(publicId.trim())}?${params.toString()}`,
  )
}

export async function createBackendPortalTicketReply(
  marketCode: string,
  publicId: string,
  input: BackendPortalTicketReplyInput,
): Promise<BackendPortalTicketDetail> {
  return fetchJson<BackendPortalTicketDetail>(
    `/portal/${encodeURIComponent(marketCode.toLowerCase())}/tickets/${encodeURIComponent(publicId.trim())}/reply`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export async function uploadBackendPortalAttachment(
  marketCode: string,
  publicId: string,
  email: string,
  file: File,
): Promise<BackendPortalAttachment> {
  const params = new URLSearchParams()
  appendDefinedQuery(params, 'email', email)
  appendDefinedQuery(params, 'filename', file.name || 'attachment')
  const response = await fetch(
    `${getBackendBaseUrl()}/portal/${encodeURIComponent(marketCode.toLowerCase())}/tickets/${encodeURIComponent(publicId.trim())}/attachments?${params.toString()}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
      },
      body: file,
    },
  )

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`.trim()
    try {
      const errorBody = (await response.json()) as { detail?: string }
      if (errorBody.detail) message = errorBody.detail
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new Error(message)
  }

  return response.json() as Promise<BackendPortalAttachment>
}

export async function patchBackendTicket(
  ticketId: string,
  patch: BackendUpdateTicketInput,
  session: BackendSession,
): Promise<BackendTicket> {
  return fetchJson<BackendTicket>(
    `/tickets/${ticketId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function fetchBackendDuplicateTickets(
  ticketId: string,
  session: BackendSession,
  limit = 5,
): Promise<BackendDuplicateTicketSuggestion[]> {
  return fetchJson<BackendDuplicateTicketSuggestion[]>(
    `/tickets/${ticketId}/duplicate-suggestions?limit=${encodeURIComponent(String(limit))}`,
    undefined,
    session,
  )
}

export async function mergeBackendTickets(
  ticketId: string,
  input: BackendMergeTicketsInput,
  session: BackendSession,
): Promise<BackendMergeTicketsResponse> {
  return fetchJson<BackendMergeTicketsResponse>(
    `/tickets/${ticketId}/merge`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function createBackendTicketField(
  input: BackendCreateTicketFieldInput,
  session: BackendSession,
): Promise<BackendTicketField> {
  return fetchJson<BackendTicketField>(
    '/ticket-fields',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendTicketField(
  fieldId: string,
  patch: BackendUpdateTicketFieldInput,
  session: BackendSession,
): Promise<BackendTicketField> {
  return fetchJson<BackendTicketField>(
    `/ticket-fields/${fieldId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function postBackendReply(
  ticketId: string,
  input: BackendReplyInput,
  session: BackendSession,
): Promise<BackendTimelineEvent> {
  return fetchJson<BackendTimelineEvent>(
    `/tickets/${ticketId}/reply`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function createBackendAttachment(
  ticketId: string,
  input: BackendCreateAttachmentInput,
  session: BackendSession,
): Promise<BackendAttachment> {
  return fetchJson<BackendAttachment>(
    `/tickets/${ticketId}/attachments`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function uploadBackendAttachment(
  ticketId: string,
  file: File,
  session: BackendSession,
): Promise<BackendAttachment> {
  const headers = new Headers()
  for (const [key, value] of Object.entries(authHeaders(session))) {
    if (value) headers.set(key, value)
  }
  headers.set('Content-Type', file.type || 'application/octet-stream')
  const response = await fetch(
    `${getBackendBaseUrl()}/tickets/${ticketId}/attachments/binary?filename=${encodeURIComponent(file.name || 'attachment')}`,
    {
      method: 'POST',
      headers,
      body: file,
    },
  )

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`.trim()
    try {
      const errorBody = (await response.json()) as { detail?: string }
      if (errorBody.detail) message = errorBody.detail
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new Error(message)
  }

  return response.json() as Promise<BackendAttachment>
}

export async function createBackendHandoff(
  ticketId: string,
  input: BackendCreateHandoffInput,
  session: BackendSession,
): Promise<BackendHandoff> {
  return fetchJson<BackendHandoff>(
    `/tickets/${ticketId}/handoffs`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendHandoff(
  handoffId: string,
  patch: BackendUpdateHandoffInput,
  session: BackendSession,
): Promise<BackendHandoff> {
  return fetchJson<BackendHandoff>(
    `/handoffs/${handoffId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function patchBackendChannel(
  channelId: string,
  patch: BackendUpdateChannelInput,
  session: BackendSession,
): Promise<BackendChannel> {
  return fetchJson<BackendChannel>(
    `/channels/${channelId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function patchBackendKnowledgeArticle(
  articleId: string,
  patch: BackendUpdateKnowledgeInput,
  session: BackendSession,
): Promise<BackendKnowledgeArticle> {
  return fetchJson<BackendKnowledgeArticle>(
    `/knowledge/${articleId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function recordBackendResponseMacroUse(
  macroId: string,
  ticketId: string,
  session: BackendSession,
): Promise<BackendResponseMacro> {
  const params = new URLSearchParams()
  params.set('ticket_id', ticketId)
  return fetchJson<BackendResponseMacro>(
    `/macros/${macroId}/use?${params.toString()}`,
    {
      method: 'POST',
    },
    session,
  )
}

export async function createBackendResponseMacro(
  input: BackendCreateResponseMacroInput,
  session: BackendSession,
): Promise<BackendResponseMacro> {
  return fetchJson<BackendResponseMacro>(
    '/macros',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendResponseMacro(
  macroId: string,
  patch: BackendUpdateResponseMacroInput,
  session: BackendSession,
): Promise<BackendResponseMacro> {
  return fetchJson<BackendResponseMacro>(
    `/macros/${macroId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function patchBackendAutomationRule(
  ruleId: string,
  patch: BackendUpdateRuleInput,
  session: BackendSession,
): Promise<BackendAutomationRule> {
  return fetchJson<BackendAutomationRule>(
    `/automation-rules/${ruleId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function retryBackendOutboundMessage(
  messageId: string,
  session: BackendSession,
): Promise<BackendOutboundMessage> {
  return fetchJson<BackendOutboundMessage>(
    `/outbound/messages/${messageId}/retry`,
    {
      method: 'POST',
      body: JSON.stringify({ reason: 'Manual retry from Setup' }),
    },
    session,
  )
}

export async function patchBackendOperationalAlert(
  alertId: string,
  patch: BackendUpdateOperationalAlertInput,
  session: BackendSession,
): Promise<BackendOperationalAlert> {
  return fetchJson<BackendOperationalAlert>(
    `/alerts/${alertId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}
