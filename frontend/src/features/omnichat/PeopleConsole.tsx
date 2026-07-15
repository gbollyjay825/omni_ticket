import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Mail,
  MapPin,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Tags,
  Users,
} from 'lucide-react'
import { useDeferredValue, useMemo, useState, type FormEvent } from 'react'

import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'
import type { BackendSession } from '../../backend'

type Customer = components['schemas']['Customer']
type Segment = components['schemas']['SegmentResponse']
type Sentiment = components['schemas']['Sentiment']
type CampaignConsent = components['schemas']['CampaignConsentResponse']
type CampaignChannel = components['schemas']['SetCampaignConsentRequest']['channel']

const PAGE_SIZE = 50
const sentiments: Sentiment[] = ['positive', 'neutral', 'frustrated', 'angry']
const channelOptions = ['email', 'whatsapp', 'sms', 'facebook', 'instagram', 'portal']
const campaignChannels: CampaignChannel[] = ['whatsapp', 'sms', 'facebook', 'instagram']

interface PeopleConsoleProps {
  session: BackendSession | null
  canManage: boolean
  onOpenCustomer: (customerId: string) => void
  onOpenContacts: () => void
}

interface CustomerPage {
  items: Customer[]
  total: number
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'detail' in error && typeof error.detail === 'string') {
    return error.detail
  }
  return 'People data is unavailable.'
}

function splitValues(value: string) {
  return [...new Set(value.split(',').map((item) => item.trim().toLowerCase()).filter(Boolean))]
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

function segmentRuleSummary(segment: Segment) {
  if (segment.rules.include_all) return 'All contacts in the active market'
  const rules: string[] = []
  if (segment.rules.tags_any?.length) rules.push(`Any tag: ${segment.rules.tags_any.join(', ')}`)
  if (segment.rules.tags_all?.length) rules.push(`All tags: ${segment.rules.tags_all.join(', ')}`)
  if (segment.rules.sentiments?.length) {
    rules.push(`Sentiment: ${segment.rules.sentiments.join(', ')}`)
  }
  if (segment.rules.preferred_channels_any?.length) {
    rules.push(`Channels: ${segment.rules.preferred_channels_any.join(', ')}`)
  }
  return rules.join(' / ')
}

export function PeopleConsole({
  session,
  canManage,
  onOpenCustomer,
  onOpenContacts,
}: PeopleConsoleProps) {
  const client = useMemo(() => createOmniApiClient(session), [session])
  const queryClient = useQueryClient()
  const [view, setView] = useState<'people' | 'segments' | 'consent'>('people')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search.trim())
  const [sentiment, setSentiment] = useState<Sentiment | ''>('')
  const [page, setPage] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const [consentFormOpen, setConsentFormOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState({
    name: '',
    description: '',
    tagsAny: '',
    tagsAll: '',
    channels: [] as string[],
    sentiments: [] as Sentiment[],
    includeAll: false,
  })
  const [consentDraft, setConsentDraft] = useState({
    customerId: '',
    channel: 'whatsapp' as CampaignChannel,
    status: 'opted_in' as 'opted_in' | 'opted_out',
    source: '',
    evidence: '',
  })

  const customersQuery = useQuery({
    queryKey: ['omnichat-people', session?.market.id, deferredSearch, sentiment, page],
    enabled: Boolean(session),
    queryFn: async (): Promise<CustomerPage> => {
      const response = await client.GET('/api/v1/customers', {
        params: {
          query: {
            q: deferredSearch || undefined,
            sentiment: sentiment || undefined,
            sort_by: 'name',
            sort_order: 'asc',
            limit: PAGE_SIZE,
            offset: page * PAGE_SIZE,
          },
        },
      })
      if (response.error) throw response.error
      return {
        items: response.data ?? [],
        total: Number(response.response.headers.get('X-Total-Count') ?? response.data?.length ?? 0),
      }
    },
  })

  const segmentsQuery = useQuery({
    queryKey: ['segments', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<Segment[]> => {
      const response = await client.GET('/api/v1/segments')
      if (response.error) throw response.error
      return response.data ?? []
    },
  })

  const consentsQuery = useQuery({
    queryKey: ['campaign-consents', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<CampaignConsent[]> => {
      const response = await client.GET('/api/v1/campaigns/consents')
      if (response.error) throw response.error
      return response.data ?? []
    },
  })

  const createSegment = useMutation({
    mutationFn: async () => {
      const response = await client.POST('/api/v1/segments', {
        body: {
          name: draft.name.trim(),
          description: draft.description.trim(),
          rules: {
            include_all: draft.includeAll,
            tags_any: splitValues(draft.tagsAny),
            tags_all: splitValues(draft.tagsAll),
            preferred_channels_any: draft.channels,
            sentiments: draft.sentiments,
            company_ids: [],
          },
        },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (segment) => {
      await queryClient.invalidateQueries({ queryKey: ['segments', session?.market.id] })
      setDraft({
        name: '',
        description: '',
        tagsAny: '',
        tagsAll: '',
        channels: [],
        sentiments: [],
        includeAll: false,
      })
      setFormOpen(false)
      setNotice(`${segment?.name ?? 'Segment'} created.`)
    },
  })

  const updateSegment = useMutation({
    mutationFn: async ({ id, active }: { id: string; active: boolean }) => {
      const response = await client.PATCH('/api/v1/segments/{segment_id}', {
        params: { path: { segment_id: id } },
        body: { active },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (segment) => {
      await queryClient.invalidateQueries({ queryKey: ['segments', session?.market.id] })
      setNotice(`${segment?.name ?? 'Segment'} is now ${segment?.active ? 'active' : 'paused'}.`)
    },
  })

  const setConsent = useMutation({
    mutationFn: async (input: typeof consentDraft) => {
      const response = await client.PUT('/api/v1/campaigns/consents', {
        body: {
          customer_id: input.customerId,
          channel: input.channel,
          status: input.status,
          source: input.source.trim(),
          evidence: input.evidence.trim(),
        },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (consent) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['campaign-consents', session?.market.id] }),
        queryClient.invalidateQueries({ queryKey: ['campaigns', session?.market.id] }),
      ])
      setConsentDraft({
        customerId: '',
        channel: 'whatsapp',
        status: 'opted_in',
        source: '',
        evidence: '',
      })
      setConsentFormOpen(false)
      setNotice(
        `${consent?.customer_name ?? 'Customer'} is ${consent?.status === 'opted_in' ? 'opted in' : 'opted out'} for ${consent?.channel ?? 'campaigns'}.`,
      )
    },
  })

  const totalCustomers = customersQuery.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(totalCustomers / PAGE_SIZE))
  const hasRules = Boolean(
    draft.includeAll ||
      splitValues(draft.tagsAny).length ||
      splitValues(draft.tagsAll).length ||
      draft.channels.length ||
      draft.sentiments.length,
  )
  const canSubmit = canManage && draft.name.trim().length >= 2 && hasRules

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (canSubmit && !createSegment.isPending) createSegment.mutate()
  }

  function toggleChannel(channel: string) {
    setDraft((current) => ({
      ...current,
      channels: current.channels.includes(channel)
        ? current.channels.filter((item) => item !== channel)
        : [...current.channels, channel],
    }))
  }

  function toggleSentiment(value: Sentiment) {
    setDraft((current) => ({
      ...current,
      sentiments: current.sentiments.includes(value)
        ? current.sentiments.filter((item) => item !== value)
        : [...current.sentiments, value],
    }))
  }

  function submitConsent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (
      canManage &&
      consentDraft.customerId &&
      consentDraft.source.trim().length >= 2 &&
      !setConsent.isPending
    ) {
      setConsent.mutate(consentDraft)
    }
  }

  const queryError = customersQuery.error ?? segmentsQuery.error ?? consentsQuery.error
  if (queryError) {
    return (
      <div className="report-catalog-state error" role="alert">
        <AlertTriangle size={16} />
        <span>{errorMessage(queryError)}</span>
        <button
          type="button"
          onClick={() => {
            void customersQuery.refetch()
            void segmentsQuery.refetch()
            void consentsQuery.refetch()
          }}
        >
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="people-console">
      <div className="people-console-toolbar">
        <div className="people-console-tabs" role="tablist" aria-label="People workspace">
          <button
            type="button"
            role="tab"
            aria-selected={view === 'people'}
            className={view === 'people' ? 'active' : ''}
            onClick={() => setView('people')}
          >
            <Users size={14} />
            People
            <span>{totalCustomers}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === 'segments'}
            className={view === 'segments' ? 'active' : ''}
            onClick={() => setView('segments')}
          >
            <Tags size={14} />
            Segments
            <span>{segmentsQuery.data?.length ?? 0}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === 'consent'}
            className={view === 'consent' ? 'active' : ''}
            onClick={() => setView('consent')}
          >
            <ShieldCheck size={14} />
            Consent
            <span>{consentsQuery.data?.length ?? 0}</span>
          </button>
        </div>
        {view === 'people' ? (
          <button type="button" className="secondary-action" onClick={onOpenContacts}>
            Open Contacts
          </button>
        ) : view === 'segments' ? (
          <button
            type="button"
            className="primary-action"
            onClick={() => setFormOpen((open) => !open)}
            disabled={!canManage}
          >
            <Plus size={14} />
            New segment
          </button>
        ) : (
          <button
            type="button"
            className="primary-action"
            onClick={() => setConsentFormOpen((open) => !open)}
            disabled={!canManage}
          >
            <Plus size={14} />
            Record consent
          </button>
        )}
      </div>

      {notice ? <p className="campaign-notice" role="status">{notice}</p> : null}
      {createSegment.error || updateSegment.error || setConsent.error ? (
        <p className="campaign-notice error" role="alert">
          {errorMessage(createSegment.error ?? updateSegment.error ?? setConsent.error)}
        </p>
      ) : null}

      {view === 'people' ? (
        <>
          <div className="people-filter-row">
            <label>
              <Search size={15} />
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value)
                  setPage(0)
                }}
                placeholder="Search name, email, location, or notes"
                aria-label="Search people"
              />
            </label>
            <select
              value={sentiment}
              onChange={(event) => {
                setSentiment(event.target.value as Sentiment | '')
                setPage(0)
              }}
              aria-label="Filter people by sentiment"
            >
              <option value="">All sentiment</option>
              {sentiments.map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </div>
          {customersQuery.isPending ? (
            <p className="report-catalog-state">Loading people...</p>
          ) : customersQuery.data?.items.length ? (
            <div className="people-directory" aria-label="People directory">
              {customersQuery.data.items.map((customer) => (
                <button
                  type="button"
                  key={customer.id}
                  className="people-directory-row"
                  onClick={() => onOpenCustomer(customer.id)}
                >
                  <span className="people-avatar" aria-hidden="true">{initials(customer.name)}</span>
                  <span className="people-identity">
                    <strong>{customer.name}</strong>
                    <span><Mail size={12} /> {customer.email}</span>
                  </span>
                  <span className="people-context">
                    <span><MapPin size={12} /> {customer.location || 'Location not provided'}</span>
                    <span>{customer.preferred_channels?.join(', ') || 'No preferred channel'}</span>
                  </span>
                  <span className="people-tags">
                    {customer.tags?.slice(0, 2).map((tag) => <em key={tag}>{tag}</em>)}
                  </span>
                  <span className={`people-sentiment sentiment-${customer.sentiment}`}>
                    {customer.sentiment}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="campaign-empty">
              <Users size={20} />
              <strong>No matching people</strong>
              <span>Change the search or sentiment filter.</span>
            </div>
          )}
          <div className="people-pagination">
            <span>
              {totalCustomers
                ? `${page * PAGE_SIZE + 1}-${Math.min((page + 1) * PAGE_SIZE, totalCustomers)} of ${totalCustomers}`
                : '0 people'}
            </span>
            <div>
              <button
                type="button"
                aria-label="Previous people page"
                disabled={page === 0}
                onClick={() => setPage((current) => Math.max(0, current - 1))}
              >
                <ChevronLeft size={15} />
              </button>
              <span>{page + 1} / {totalPages}</span>
              <button
                type="button"
                aria-label="Next people page"
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((current) => current + 1)}
              >
                <ChevronRight size={15} />
              </button>
            </div>
          </div>
        </>
      ) : view === 'segments' ? (
        <>
          {formOpen ? (
            <form className="segment-form" onSubmit={submit}>
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
                <span>Description</span>
                <input
                  value={draft.description}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, description: event.target.value }))
                  }
                  maxLength={500}
                />
              </label>
              <label>
                <span>Match any tag</span>
                <input
                  value={draft.tagsAny}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, tagsAny: event.target.value }))
                  }
                  placeholder="vip, payment-risk"
                  disabled={draft.includeAll}
                />
              </label>
              <label>
                <span>Require all tags</span>
                <input
                  value={draft.tagsAll}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, tagsAll: event.target.value }))
                  }
                  placeholder="corporate, active"
                  disabled={draft.includeAll}
                />
              </label>
              <fieldset disabled={draft.includeAll}>
                <legend>Preferred channels</legend>
                <div>
                  {channelOptions.map((channel) => (
                    <label key={channel}>
                      <input
                        type="checkbox"
                        checked={draft.channels.includes(channel)}
                        onChange={() => toggleChannel(channel)}
                      />
                      <span>{channel}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <fieldset disabled={draft.includeAll}>
                <legend>Sentiment</legend>
                <div>
                  {sentiments.map((value) => (
                    <label key={value}>
                      <input
                        type="checkbox"
                        checked={draft.sentiments.includes(value)}
                        onChange={() => toggleSentiment(value)}
                      />
                      <span>{value}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="segment-include-all">
                <input
                  type="checkbox"
                  checked={draft.includeAll}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, includeAll: event.target.checked }))
                  }
                />
                <span>Include all contacts in this market</span>
              </label>
              <div className="campaign-form-actions">
                <button type="button" onClick={() => setFormOpen(false)}>Cancel</button>
                <button type="submit" className="primary-action" disabled={!canSubmit || createSegment.isPending}>
                  {createSegment.isPending ? <RefreshCw size={14} className="spin-icon" /> : <Plus size={14} />}
                  Create segment
                </button>
              </div>
            </form>
          ) : null}
          {segmentsQuery.isPending ? (
            <p className="report-catalog-state">Loading segments...</p>
          ) : segmentsQuery.data?.length ? (
            <div className="segment-list">
              {segmentsQuery.data.map((segment) => (
                <article key={segment.id}>
                  <div>
                    <span className="segment-icon"><Tags size={15} /></span>
                    <span>
                      <strong>{segment.name}</strong>
                      <small>{segment.description || segmentRuleSummary(segment)}</small>
                    </span>
                  </div>
                  <p>{segmentRuleSummary(segment)}</p>
                  <strong>{segment.member_count}<span> people</span></strong>
                  <button
                    type="button"
                    disabled={!canManage || updateSegment.isPending}
                    onClick={() => updateSegment.mutate({ id: segment.id, active: !segment.active })}
                  >
                    {segment.active ? 'Pause' : 'Activate'}
                  </button>
                  <em className={`chip status-${segment.active ? 'done' : 'pending'}`}>
                    {segment.active ? 'Active' : 'Paused'}
                  </em>
                </article>
              ))}
            </div>
          ) : (
            <div className="campaign-empty">
              <Tags size={20} />
              <strong>No segments in this market</strong>
              <span>Create a reusable audience from customer attributes.</span>
            </div>
          )}
        </>
      ) : (
        <>
          {consentFormOpen ? (
            <form className="segment-form consent-form" onSubmit={submitConsent}>
              <label>
                <span>Customer</span>
                <select
                  value={consentDraft.customerId}
                  onChange={(event) =>
                    setConsentDraft((current) => ({ ...current, customerId: event.target.value }))
                  }
                  required
                >
                  <option value="">Select a customer</option>
                  {customersQuery.data?.items.map((customer) => (
                    <option key={customer.id} value={customer.id}>{customer.name} - {customer.email}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Channel</span>
                <select
                  value={consentDraft.channel}
                  onChange={(event) =>
                    setConsentDraft((current) => ({
                      ...current,
                      channel: event.target.value as CampaignChannel,
                    }))
                  }
                >
                  {campaignChannels.map((channel) => <option key={channel} value={channel}>{channel}</option>)}
                </select>
              </label>
              <label>
                <span>Status</span>
                <select
                  value={consentDraft.status}
                  onChange={(event) =>
                    setConsentDraft((current) => ({
                      ...current,
                      status: event.target.value as 'opted_in' | 'opted_out',
                    }))
                  }
                >
                  <option value="opted_in">Opted in</option>
                  <option value="opted_out">Opted out</option>
                </select>
              </label>
              <label>
                <span>Source</span>
                <input
                  value={consentDraft.source}
                  onChange={(event) =>
                    setConsentDraft((current) => ({ ...current, source: event.target.value }))
                  }
                  placeholder="Booking checkout"
                  required
                />
              </label>
              <label className="consent-evidence">
                <span>Evidence</span>
                <input
                  value={consentDraft.evidence}
                  onChange={(event) =>
                    setConsentDraft((current) => ({ ...current, evidence: event.target.value }))
                  }
                  placeholder="Preference event, form, or message reference"
                />
              </label>
              <div className="campaign-form-actions">
                <button type="button" onClick={() => setConsentFormOpen(false)}>Cancel</button>
                <button
                  type="submit"
                  className="primary-action"
                  disabled={
                    !canManage ||
                    !consentDraft.customerId ||
                    consentDraft.source.trim().length < 2 ||
                    setConsent.isPending
                  }
                >
                  {setConsent.isPending ? <RefreshCw size={14} className="spin-icon" /> : <ShieldCheck size={14} />}
                  Save consent
                </button>
              </div>
            </form>
          ) : null}
          {consentsQuery.isPending ? (
            <p className="report-catalog-state">Loading consent records...</p>
          ) : consentsQuery.data?.length ? (
            <div className="consent-list" aria-label="Campaign consent records">
              {consentsQuery.data.map((consent) => (
                <article key={consent.id}>
                  <span className="settings-record-icon"><ShieldCheck size={15} /></span>
                  <span>
                    <strong>{consent.customer_name}</strong>
                    <small>{consent.customer_email}</small>
                  </span>
                  <span>
                    <strong>{consent.channel}</strong>
                    <small>{consent.source}</small>
                  </span>
                  <span>
                    <strong>{consent.captured_by}</strong>
                    <small>{new Date(consent.captured_at).toLocaleString()}</small>
                  </span>
                  <em className={`chip status-${consent.status === 'opted_in' ? 'done' : 'pending'}`}>
                    {consent.status === 'opted_in' ? 'Opted in' : 'Opted out'}
                  </em>
                </article>
              ))}
            </div>
          ) : (
            <div className="campaign-empty">
              <ShieldCheck size={20} />
              <strong>No campaign consent recorded</strong>
              <span>Campaign delivery remains blocked until a source-backed opt-in exists.</span>
            </div>
          )}
        </>
      )}
    </div>
  )
}
