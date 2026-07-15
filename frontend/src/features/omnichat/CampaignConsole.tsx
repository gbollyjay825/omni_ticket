import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Pause, Play, Plus, RefreshCw, Send, Settings, Users } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'

import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'
import type { BackendSession } from '../../backend'

type Campaign = components['schemas']['CampaignResponse']
type CampaignChannel = Campaign['channel']
type CampaignReadiness = components['schemas']['CampaignProviderReadiness']

const channelLabels: Record<CampaignChannel, string> = {
  whatsapp: 'WhatsApp',
  sms: 'SMS',
  facebook: 'Facebook',
  instagram: 'Instagram',
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'detail' in error && typeof error.detail === 'string') {
    return error.detail
  }
  return 'Campaigns are unavailable.'
}

interface CampaignConsoleProps {
  session: BackendSession | null
  canManage: boolean
  onOpenSettings: () => void
}

export function CampaignConsole({ session, canManage, onOpenSettings }: CampaignConsoleProps) {
  const client = useMemo(() => createOmniApiClient(session), [session])
  const queryClient = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState({
    name: '',
    channel: 'whatsapp' as CampaignChannel,
    messageBody: '',
    tags: '',
    includeAll: false,
    scheduledAt: '',
    templateName: '',
    templateLanguage: 'en_US',
    templateVariables: '',
  })

  const campaignsQuery = useQuery({
    queryKey: ['campaigns', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<Campaign[]> => {
      const response = await client.GET('/api/v1/campaigns')
      if (response.error) throw response.error
      return response.data ?? []
    },
  })
  const readinessQuery = useQuery({
    queryKey: ['campaign-readiness', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<CampaignReadiness[]> => {
      const response = await client.GET('/api/v1/campaigns/readiness')
      if (response.error) throw response.error
      return response.data ?? []
    },
  })

  const createCampaign = useMutation({
    mutationFn: async () => {
      const response = await client.POST('/api/v1/campaigns', {
        body: {
          name: draft.name.trim(),
          channel: draft.channel,
          message_body: draft.messageBody.trim(),
          audience: {
            include_all: draft.includeAll,
            tags_any: draft.tags
              .split(',')
              .map((tag) => tag.trim())
              .filter(Boolean),
          },
          scheduled_at: draft.scheduledAt ? new Date(draft.scheduledAt).toISOString() : null,
          template_name: draft.templateName.trim(),
          template_language: draft.templateLanguage.trim() || 'en_US',
          template_variables: draft.templateVariables
            .split(',')
            .map((value) => value.trim())
            .filter(Boolean),
        },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (campaign) => {
      if (campaign) {
        queryClient.setQueryData<Campaign[]>(
          ['campaigns', session?.market.id],
          (current = []) => [campaign, ...current.filter((item) => item.id !== campaign.id)],
        )
      }
      void queryClient.invalidateQueries({ queryKey: ['campaigns', session?.market.id] })
      setDraft({
        name: '',
        channel: 'whatsapp',
        messageBody: '',
        tags: '',
        includeAll: false,
        scheduledAt: '',
        templateName: '',
        templateLanguage: 'en_US',
        templateVariables: '',
      })
      setFormOpen(false)
      setNotice(`${campaign?.name ?? 'Campaign'} saved as a draft.`)
    },
  })

  const updateCampaign = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: Campaign['status'] }) => {
      const response = await client.PATCH('/api/v1/campaigns/{campaign_id}', {
        params: { path: { campaign_id: id } },
        body: { status },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (campaign) => {
      await queryClient.invalidateQueries({ queryKey: ['campaigns', session?.market.id] })
      setNotice(`${campaign?.name ?? 'Campaign'} is ${campaign?.status ?? 'updated'}.`)
    },
  })

  const launchCampaign = useMutation({
    mutationFn: async (id: string) => {
      const response = await client.POST('/api/v1/campaigns/{campaign_id}/launch', {
        params: { path: { campaign_id: id } },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['campaigns', session?.market.id] })
      const count = result?.created_deliveries ?? 0
      setNotice(
        count
          ? `${result?.campaign.name ?? 'Campaign'} queued for ${count} consented contact${count === 1 ? '' : 's'}.`
          : `${result?.campaign.name ?? 'Campaign'} was already launched.`,
      )
    },
  })

  const selectedReadiness = readinessQuery.data?.find((item) => item.channel === draft.channel)
  const tagsSelected = draft.tags.split(',').some((tag) => tag.trim())
  const canSubmit =
    canManage &&
    draft.name.trim().length >= 2 &&
    draft.messageBody.trim().length >= 2 &&
    (draft.includeAll || tagsSelected)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (canSubmit && !createCampaign.isPending) createCampaign.mutate()
  }

  if (campaignsQuery.error || readinessQuery.error) {
    return (
      <div className="report-catalog-state error" role="alert">
        <AlertTriangle size={16} />
        <span>{errorMessage(campaignsQuery.error ?? readinessQuery.error)}</span>
        <button
          type="button"
          onClick={() => {
            void campaignsQuery.refetch()
            void readinessQuery.refetch()
          }}
        >
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="campaign-console">
      <div className="campaign-toolbar">
        <div>
          <strong>{campaignsQuery.data?.length ?? 0} campaigns</strong>
          <span>Draft and paused outreach for the active market</span>
        </div>
        <button
          type="button"
          className="primary-action"
          onClick={() => setFormOpen((open) => !open)}
          disabled={!canManage}
        >
          <Plus size={14} />
          New campaign
        </button>
      </div>

      {notice ? <p className="campaign-notice" role="status">{notice}</p> : null}
      {createCampaign.error || updateCampaign.error || launchCampaign.error ? (
        <p className="campaign-notice error" role="alert">
          {errorMessage(createCampaign.error ?? updateCampaign.error ?? launchCampaign.error)}
        </p>
      ) : null}

      {formOpen ? (
        <form className="campaign-form" onSubmit={submit}>
          <label>
            <span>Name</span>
            <input
              value={draft.name}
              onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
              maxLength={180}
              required
            />
          </label>
          <label>
            <span>Channel</span>
            <select
              value={draft.channel}
              onChange={(event) =>
                setDraft((current) => ({ ...current, channel: event.target.value as CampaignChannel }))
              }
            >
              {(Object.keys(channelLabels) as CampaignChannel[]).map((channel) => (
                <option key={channel} value={channel}>{channelLabels[channel]}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Audience tags</span>
            <input
              value={draft.tags}
              onChange={(event) => setDraft((current) => ({ ...current, tags: event.target.value }))}
              placeholder="vip, flight-change"
            />
          </label>
          <label>
            <span>Schedule</span>
            <input
              type="datetime-local"
              value={draft.scheduledAt}
              onChange={(event) =>
                setDraft((current) => ({ ...current, scheduledAt: event.target.value }))
              }
            />
          </label>
          <label className="campaign-audience-all">
            <input
              type="checkbox"
              checked={draft.includeAll}
              onChange={(event) =>
                setDraft((current) => ({ ...current, includeAll: event.target.checked }))
              }
            />
            <span>Include all addressable contacts</span>
          </label>
          <label className="campaign-message">
            <span>Message</span>
            <textarea
              value={draft.messageBody}
              onChange={(event) =>
                setDraft((current) => ({ ...current, messageBody: event.target.value }))
              }
              maxLength={4000}
              required
            />
          </label>
          {draft.channel === 'whatsapp' ? (
            <div className="campaign-template-fields">
              <label>
                <span>Approved template</span>
                <input
                  value={draft.templateName}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, templateName: event.target.value }))
                  }
                  placeholder="booking_update"
                />
              </label>
              <label>
                <span>Template language</span>
                <input
                  value={draft.templateLanguage}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, templateLanguage: event.target.value }))
                  }
                  placeholder="en_US"
                />
              </label>
              <label>
                <span>Body variables</span>
                <input
                  value={draft.templateVariables}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, templateVariables: event.target.value }))
                  }
                  placeholder="Customer name, booking reference"
                />
              </label>
            </div>
          ) : null}
          <div className={`campaign-readiness ${selectedReadiness?.configured ? 'ready' : 'blocked'}`}>
            <span>{selectedReadiness?.configured ? 'Connected' : 'Not configured'}</span>
            <small>{selectedReadiness?.detail ?? 'Checking provider readiness...'}</small>
            {!selectedReadiness?.configured ? (
              <button type="button" onClick={onOpenSettings}>
                <Settings size={13} />
                Setup
              </button>
            ) : null}
          </div>
          <div className="campaign-form-actions">
            <button type="button" onClick={() => setFormOpen(false)}>Cancel</button>
            <button type="submit" className="primary-action" disabled={!canSubmit || createCampaign.isPending}>
              {createCampaign.isPending ? <RefreshCw size={14} className="spin-icon" /> : <Plus size={14} />}
              Save draft
            </button>
          </div>
        </form>
      ) : null}

      {campaignsQuery.isPending ? <p className="report-catalog-state">Loading campaigns...</p> : null}
      {!campaignsQuery.isPending && !campaignsQuery.data?.length ? (
        <div className="campaign-empty">
          <Users size={20} />
          <strong>No campaigns in this market</strong>
          <span>Create an audience-specific outreach draft.</span>
        </div>
      ) : null}
      {campaignsQuery.data?.length ? (
        <div className="campaign-list">
          {campaignsQuery.data.map((campaign) => (
            <article key={campaign.id}>
              <div className="campaign-row-head">
                <div>
                  <strong>{campaign.name}</strong>
                  <span>
                    {channelLabels[campaign.channel]} · {campaign.consented_recipients} consented / {campaign.estimated_recipients} addressable
                  </span>
                </div>
                <em className={`chip status-${campaign.status === 'completed' ? 'done' : campaign.status === 'running' ? 'progress' : 'pending'}`}>
                  {campaign.status.replace('_', ' ')}
                </em>
              </div>
              <p>{campaign.message_body}</p>
              {campaign.delivery_summary.total ? (
                <div className="campaign-delivery-summary" aria-label={`${campaign.name} delivery status`}>
                  <span><strong>{campaign.delivery_summary.total}</strong><small>Total</small></span>
                  <span><strong>{campaign.delivery_summary.queued + campaign.delivery_summary.sending}</strong><small>Pending</small></span>
                  <span><strong>{campaign.delivery_summary.sent + campaign.delivery_summary.delivered + campaign.delivery_summary.read}</strong><small>Accepted</small></span>
                  <span><strong>{campaign.delivery_summary.failed + campaign.delivery_summary.dead_lettered}</strong><small>Failed</small></span>
                  <span><strong>{campaign.delivery_summary.suppressed}</strong><small>Suppressed</small></span>
                </div>
              ) : null}
              <div className="campaign-row-meta">
                <span>{campaign.audience.include_all ? 'All contacts' : campaign.audience.tags_any?.join(', ')}</span>
                <span className={campaign.provider.configured ? 'provider-ready' : 'provider-blocked'}>
                  {campaign.provider.configured ? 'Provider connected' : 'Provider not configured'}
                </span>
                {campaign.status === 'draft' ? (
                  <button
                    type="button"
                    disabled={
                      !canManage ||
                      launchCampaign.isPending ||
                      !campaign.provider.configured ||
                      campaign.consented_recipients === 0 ||
                      (campaign.channel === 'whatsapp' && !campaign.template_name)
                    }
                    onClick={() => launchCampaign.mutate(campaign.id)}
                  >
                    <Send size={13} />
                    Launch
                  </button>
                ) : campaign.status === 'scheduled' || campaign.status === 'running' ? (
                  <button
                    type="button"
                    disabled={!canManage || updateCampaign.isPending}
                    onClick={() => updateCampaign.mutate({ id: campaign.id, status: 'paused' })}
                  >
                    <Pause size={13} />
                    Pause
                  </button>
                ) : campaign.status === 'paused' ? (
                  <button
                    type="button"
                    disabled={!canManage || updateCampaign.isPending}
                    onClick={() =>
                      updateCampaign.mutate({
                        id: campaign.id,
                        status: campaign.delivery_summary.total ? 'running' : 'draft',
                      })
                    }
                  >
                    <Play size={13} />
                    Resume
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </div>
  )
}
