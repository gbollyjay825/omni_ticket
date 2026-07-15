import { useEffect, useMemo, useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import {
  BookOpen,
  Clock,
  Globe2,
  LifeBuoy,
  Lock,
  Mail,
  MessageSquare,
  Paperclip,
  RefreshCw,
  Search,
  Send,
  Star,
} from 'lucide-react'

import {
  createBackendPortalTicket,
  createBackendPortalTicketCsat,
  createBackendPortalTicketReply,
  fetchBackendPortalAnswers,
  fetchBackendPortalConfiguration,
  fetchBackendPortalMarkets,
  fetchBackendPortalTicket,
  uploadBackendPortalAttachment,
  type BackendCreatePortalTicketInput,
  type BackendPortalAnswerSuggestion,
  type BackendPortalConfiguration,
  type BackendPortalMarket,
  type BackendPortalTicketDetail,
  type BackendTicketField,
} from '../../backend'
import '../../App.css'

const priorityOptions: NonNullable<BackendCreatePortalTicketInput['priority']>[] = [
  'normal',
  'high',
  'urgent',
  'low',
]

const defaultMarkets: BackendPortalMarket[] = [
  { code: 'ng', name: 'Nigeria', default_locale: 'en' },
  { code: 'gh', name: 'Ghana', default_locale: 'en' },
  { code: 'uk', name: 'United Kingdom', default_locale: 'en' },
]

function titleCase(value: string) {
  return value
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function initialMarketCode() {
  const requested = new URLSearchParams(window.location.search).get('market')?.trim().toLowerCase()
  return requested || 'ng'
}

export function PortalHelpCenter() {
  const [markets, setMarkets] = useState<BackendPortalMarket[]>(defaultMarkets)
  const [marketCode, setMarketCode] = useState(initialMarketCode)
  const [configuration, setConfiguration] = useState<BackendPortalConfiguration | null>(null)
  const [configurationError, setConfigurationError] = useState('')
  const [query, setQuery] = useState('')
  const [answers, setAnswers] = useState<BackendPortalAnswerSuggestion[]>([])
  const [ticketFields, setTicketFields] = useState<BackendTicketField[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState('')
  const [searchError, setSearchError] = useState('')
  const [draft, setDraft] = useState({
    name: '',
    email: '',
    phone: '',
    subject: '',
    description: '',
    priority: 'normal' as NonNullable<BackendCreatePortalTicketInput['priority']>,
    customFields: {} as Record<string, unknown>,
  })
  const [lookup, setLookup] = useState({ publicId: '', email: '' })
  const [ticketDetail, setTicketDetail] = useState<BackendPortalTicketDetail | null>(null)
  const [csatDraft, setCsatDraft] = useState({ rating: 0, comment: '' })
  const [csatBusy, setCsatBusy] = useState(false)
  const [lookupBusy, setLookupBusy] = useState(false)
  const [replyBusy, setReplyBusy] = useState(false)
  const [replyBody, setReplyBody] = useState('')
  const [attachmentFile, setAttachmentFile] = useState<File | null>(null)
  const [replyAttachmentFile, setReplyAttachmentFile] = useState<File | null>(null)
  const [lookupNotice, setLookupNotice] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchBackendPortalMarkets()
      .then((response) => {
        if (cancelled || response.length === 0) return
        setMarkets(response)
        if (!response.some((market) => market.code === marketCode)) {
          setMarketCode(response[0].code)
        }
      })
      .catch(() => {
        if (!cancelled) setMarkets(defaultMarkets)
      })
    return () => {
      cancelled = true
    }
  }, [marketCode])

  useEffect(() => {
    let cancelled = false
    fetchBackendPortalConfiguration(marketCode)
      .then((response) => {
        if (cancelled) return
        setConfiguration(response)
        setConfigurationError('')
      })
      .catch((error) => {
        if (cancelled) return
        setConfiguration(null)
        setConfigurationError(
          error instanceof Error ? error.message : 'Help Center configuration is unavailable.',
        )
      })
    return () => {
      cancelled = true
    }
  }, [marketCode])

  useEffect(() => {
    let cancelled = false
    const searchQuery = query.trim()
    const timer = window.setTimeout(() => {
      setLoading(true)
      fetchBackendPortalAnswers(marketCode, searchQuery, 5)
        .then((response) => {
          if (cancelled) return
          setAnswers(response.suggestions)
          setTicketFields(response.ticket_fields)
          setSearchError('')
        })
        .catch((error) => {
          if (cancelled) return
          setAnswers([])
          setTicketFields([])
          setSearchError(error instanceof Error ? error.message : 'Help Center is unavailable.')
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, searchQuery ? 240 : 0)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [marketCode, query])

  const branding = useMemo(
    () => ({
      name: configuration?.public_brand_name?.trim() || 'Omni Ticket',
      supportName: configuration?.portal_support_name?.trim() || 'Wakanow support',
      accent: configuration?.portal_primary_color?.trim() || '#0b5eea',
      welcome:
        configuration?.portal_welcome_message?.trim() ||
        'Search answers or raise a support ticket',
      logoUrl: configuration?.portal_logo_url?.trim() || '',
    }),
    [configuration],
  )

  function selectMarket(code: string) {
    setMarketCode(code)
    setConfigurationError('')
    setTicketDetail(null)
    setLookupNotice('')
    const params = new URLSearchParams(window.location.search)
    params.set('screen', 'portal')
    params.set('market', code)
    window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`)
  }

  function updateCustomField(field: BackendTicketField, value: unknown) {
    setDraft((current) => ({
      ...current,
      customFields: { ...current.customFields, [field.key]: value },
    }))
  }

  function customFieldIsMissing(field: BackendTicketField, value: unknown) {
    if (field.field_type === 'checkbox') return value !== true
    return (
      value === undefined ||
      value === null ||
      value === '' ||
      (Array.isArray(value) && value.length === 0)
    )
  }

  function compactCustomFields() {
    return Object.fromEntries(
      Object.entries(draft.customFields).filter(([, value]) => {
        if (Array.isArray(value)) return value.length > 0
        return value !== undefined && value !== null && value !== ''
      }),
    )
  }

  function renderFieldInput(field: BackendTicketField) {
    const id = `portal-field-${field.id}`
    const value = draft.customFields[field.key]
    if (field.field_type === 'select') {
      return (
        <select
          id={id}
          value={typeof value === 'string' ? value : ''}
          required={field.required}
          onChange={(event) => updateCustomField(field, event.target.value)}
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
      const values = Array.isArray(value) ? value.map(String) : []
      return (
        <div className="portal-field-options" id={id}>
          {field.options.map((option) => (
            <label key={option}>
              <input
                type="checkbox"
                checked={values.includes(option)}
                onChange={(event) =>
                  updateCustomField(
                    field,
                    event.target.checked
                      ? [...values, option]
                      : values.filter((item) => item !== option),
                  )
                }
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
            onChange={(event) => updateCustomField(field, event.target.checked)}
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
          onChange={(event) => updateCustomField(field, event.target.value)}
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
          updateCustomField(
            field,
            field.field_type === 'number' && event.target.value !== ''
              ? Number(event.target.value)
              : event.target.value,
          )
        }}
      />
    )
  }

  async function uploadAttachment(publicId: string, email: string, file: File | null) {
    if (!file) return ''
    const attachment = await uploadBackendPortalAttachment(marketCode, publicId, email, file)
    if (attachment.scan_status === 'clean') return `${attachment.filename} was attached.`
    return `${attachment.filename} was received and marked ${titleCase(attachment.scan_status)}.`
  }

  async function submitTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    const name = draft.name.trim()
    const email = draft.email.trim().toLowerCase()
    const subject = draft.subject.trim()
    const description = draft.description.trim()
    if (!name || !email || !subject || !description) {
      setNotice('Name, email, subject, and details are required.')
      return
    }
    const missingField = ticketFields.find(
      (field) => field.required && customFieldIsMissing(field, draft.customFields[field.key]),
    )
    if (missingField) {
      setNotice(`${missingField.label} is required.`)
      return
    }
    setSubmitting(true)
    setNotice('')
    try {
      const response = await createBackendPortalTicket(marketCode, {
        name,
        email,
        phone: draft.phone.trim() || undefined,
        subject,
        description,
        priority: draft.priority,
        custom_fields: compactCustomFields(),
        search_query: query.trim() || subject,
      })
      if (response.article_suggestions.length) setAnswers(response.article_suggestions)
      let attachmentMessage = ''
      if (attachmentFile) {
        try {
          attachmentMessage = ` ${await uploadAttachment(response.public_id, email, attachmentFile)}`
          setAttachmentFile(null)
        } catch (error) {
          attachmentMessage = ` Ticket created, but the attachment failed: ${
            error instanceof Error ? error.message : 'upload failed'
          }.`
        }
      }
      setNotice(
        `Ticket ${response.public_id} was created. Our support team has the details.${attachmentMessage}`,
      )
      setLookup({ publicId: response.public_id, email })
      setTicketDetail(null)
      setLookupNotice('Use the check-ticket panel to follow progress or add more details.')
      setDraft((current) => ({
        ...current,
        subject: '',
        description: '',
        priority: 'normal',
        customFields: {},
      }))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Ticket submission failed.')
    } finally {
      setSubmitting(false)
    }
  }

  async function lookupTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (lookupBusy) return
    const publicId = lookup.publicId.trim().toUpperCase()
    const email = lookup.email.trim().toLowerCase()
    if (!publicId || !email) {
      setLookupNotice('Ticket number and email are required.')
      return
    }
    setLookupBusy(true)
    setLookupNotice('')
    try {
      const detail = await fetchBackendPortalTicket(marketCode, publicId, email)
      setTicketDetail(detail)
      setReplyBody('')
      setCsatDraft({ rating: 0, comment: '' })
      setAnswers(detail.article_suggestions)
      setLookup({ publicId: detail.public_id, email })
      setLookupNotice(`Ticket ${detail.public_id}: ${detail.customer_status}.`)
    } catch (error) {
      setTicketDetail(null)
      setLookupNotice(error instanceof Error ? error.message : 'Ticket lookup failed.')
    } finally {
      setLookupBusy(false)
    }
  }

  async function submitReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (replyBusy || !ticketDetail) return
    const email = lookup.email.trim().toLowerCase()
    const body = replyBody.trim()
    const file = replyAttachmentFile
    if (!email || (body.length < 2 && !file)) {
      setLookupNotice('Add a reply or attachment before sending.')
      return
    }
    setReplyBusy(true)
    setLookupNotice('')
    try {
      let detail = await createBackendPortalTicketReply(marketCode, ticketDetail.public_id, {
        email,
        body: body || `Attachment added: ${file?.name ?? 'customer file'}.`,
      })
      let attachmentMessage = ''
      if (file) {
        try {
          attachmentMessage = ` ${await uploadAttachment(detail.public_id, email, file)}`
          setReplyAttachmentFile(null)
          detail = await fetchBackendPortalTicket(marketCode, detail.public_id, email)
        } catch (error) {
          attachmentMessage = ` Reply added, but the attachment failed: ${
            error instanceof Error ? error.message : 'upload failed'
          }.`
        }
      }
      setTicketDetail(detail)
      setReplyBody('')
      setAnswers(detail.article_suggestions)
      setLookupNotice(
        `Reply added. Ticket ${detail.public_id}: ${detail.customer_status}.${attachmentMessage}`,
      )
    } catch (error) {
      setLookupNotice(error instanceof Error ? error.message : 'Reply failed.')
    } finally {
      setReplyBusy(false)
    }
  }

  async function submitCsat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (csatBusy || !ticketDetail || csatDraft.rating < 1) return
    setCsatBusy(true)
    setLookupNotice('')
    try {
      const detail = await createBackendPortalTicketCsat(marketCode, ticketDetail.public_id, {
        email: lookup.email.trim().toLowerCase(),
        rating: csatDraft.rating,
        comment: csatDraft.comment.trim() || undefined,
      })
      setTicketDetail(detail)
      setCsatDraft({ rating: 0, comment: '' })
      setLookupNotice('Thanks. Your rating has been recorded.')
    } catch (error) {
      setLookupNotice(error instanceof Error ? error.message : 'Rating failed.')
    } finally {
      setCsatBusy(false)
    }
  }

  return (
    <main
      className="portal-shell"
      style={{ '--portal-accent': branding.accent } as CSSProperties}
    >
      <header className="portal-topbar">
        <a className="portal-brand" href={`/?screen=portal&market=${marketCode}`}>
          <span className="brand-mark" style={{ background: branding.accent }}>
            {branding.logoUrl ? (
              <img src={branding.logoUrl} alt={`${branding.name} logo`} />
            ) : (
              <LifeBuoy size={22} />
            )}
          </span>
          <span>
            <strong>{branding.name}</strong>
            <small>{branding.supportName}</small>
          </span>
        </a>
        <div className="portal-topbar-actions">
          <label>
            <span>Market</span>
            <select value={marketCode} onChange={(event) => selectMarket(event.target.value)}>
              {markets.map((market) => (
                <option key={market.code} value={market.code}>
                  {market.code.toUpperCase()} - {market.name}
                </option>
              ))}
            </select>
          </label>
          <a className="secondary-action" href="/?screen=command">
            <Lock size={16} />
            Staff sign in
          </a>
        </div>
      </header>

      <section className="portal-hero">
        <div className="portal-hero-copy">
          <span className="section-kicker">Help Center</span>
          <h1>{branding.welcome}</h1>
          <form className="portal-search" onSubmit={(event) => event.preventDefault()}>
            <Search size={20} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search payments, refunds, booking changes"
              aria-label="Search Help Center answers"
            />
            {loading ? <RefreshCw size={18} className="spin-icon" /> : null}
          </form>
          {configurationError ? <strong className="portal-error">{configurationError}</strong> : null}
          {searchError ? <strong className="portal-error">{searchError}</strong> : null}
        </div>
        <div className="portal-service-strip" aria-label="Support routes">
          <article>
            <Mail size={18} />
            <strong>Email</strong>
            <span>{configuration?.support_email || 'Market support inbox'}</span>
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
                <h2>{answers.length ? `${answers.length} article(s) found` : 'No matching answer yet'}</h2>
              </div>
              <BookOpen size={20} />
            </div>
            <div className="portal-answer-list">
              {answers.map((answer) => (
                <article className="portal-answer-card" key={answer.article_id}>
                  <div>
                    <strong>{answer.title}</strong>
                    <small>
                      Updated {formatTime(answer.updated_at)}
                      {answer.language ? ` / ${answer.language.toUpperCase()}` : ''}
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
              {!loading && answers.length === 0 ? (
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
            <form className="portal-lookup-form" onSubmit={lookupTicket}>
              <label>
                Ticket number
                <input
                  value={lookup.publicId}
                  onChange={(event) =>
                    setLookup((current) => ({ ...current, publicId: event.target.value }))
                  }
                  placeholder="OMNI-1005"
                  required
                />
              </label>
              <label>
                Email
                <input
                  type="email"
                  value={lookup.email}
                  onChange={(event) =>
                    setLookup((current) => ({ ...current, email: event.target.value }))
                  }
                  required
                />
              </label>
              <button className="secondary-action" type="submit" disabled={lookupBusy}>
                {lookupBusy ? <RefreshCw size={16} className="spin-icon" /> : <Search size={16} />}
                Check
              </button>
            </form>
            {lookupNotice ? <strong className="portal-notice">{lookupNotice}</strong> : null}
            {ticketDetail ? (
              <div className="portal-ticket-detail">
                <div className="portal-ticket-summary">
                  <em
                    className={`chip status-${
                      ticketDetail.status === 'open'
                        ? 'healthy'
                        : ticketDetail.status === 'closed'
                          ? 'done'
                          : 'pending'
                    }`}
                  >
                    {ticketDetail.customer_status}
                  </em>
                  <strong>{ticketDetail.subject}</strong>
                  <p>{ticketDetail.description}</p>
                  <div className="portal-ticket-facts">
                    <span><b>Ticket</b>{ticketDetail.public_id}</span>
                    <span><b>Priority</b>{titleCase(ticketDetail.priority)}</span>
                    <span><b>Updated</b>{formatTime(ticketDetail.updated_at)}</span>
                  </div>
                  <small>{ticketDetail.next_step}</small>
                  {ticketDetail.attachments.length ? (
                    <div className="portal-attachment-list" aria-label="Customer attachments">
                      {ticketDetail.attachments.map((attachment) => (
                        <span key={attachment.id}>
                          <Paperclip size={14} />
                          {attachment.filename}
                          <small>
                            {formatFileSize(attachment.size_bytes)} / {titleCase(attachment.scan_status)}
                          </small>
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className="portal-public-timeline" aria-label="Public ticket conversation">
                  {ticketDetail.timeline.map((timelineEvent) => (
                    <article key={timelineEvent.id}>
                      <div>
                        <strong>{timelineEvent.actor}</strong>
                        <small>
                          {formatTime(timelineEvent.created_at)} / {titleCase(timelineEvent.channel)}
                        </small>
                      </div>
                      <p>{timelineEvent.body}</p>
                    </article>
                  ))}
                </div>
                <form className="portal-reply-form" onSubmit={submitReply}>
                  <label>
                    Add reply
                    <textarea value={replyBody} onChange={(event) => setReplyBody(event.target.value)} />
                  </label>
                  <label className="portal-file-field">
                    Attach file
                    <input
                      type="file"
                      onChange={(event) => setReplyAttachmentFile(event.target.files?.[0] ?? null)}
                    />
                    {replyAttachmentFile ? (
                      <small>
                        {replyAttachmentFile.name} / {formatFileSize(replyAttachmentFile.size)}
                      </small>
                    ) : null}
                  </label>
                  <button className="primary-action portal-submit" type="submit" disabled={replyBusy}>
                    {replyBusy ? <RefreshCw size={16} className="spin-icon" /> : <Send size={16} />}
                    Send reply
                  </button>
                </form>
              </div>
            ) : null}
            {ticketDetail?.csat_allowed ? (
              <div className="portal-csat" aria-label="Rate your experience">
                {ticketDetail.csat_rating ? (
                  <div className="portal-csat-done">
                    <span
                      className="portal-csat-stars"
                      aria-label={`Rated ${ticketDetail.csat_rating} out of 5`}
                    >
                      {[1, 2, 3, 4, 5].map((value) => (
                        <Star
                          key={value}
                          size={18}
                          className={value <= (ticketDetail.csat_rating ?? 0) ? 'filled' : ''}
                        />
                      ))}
                    </span>
                    <p>
                      Thanks for rating this request
                      {ticketDetail.csat_comment ? `: ${ticketDetail.csat_comment}` : ''}.
                    </p>
                  </div>
                ) : null}
                <form onSubmit={submitCsat}>
                  <strong>{ticketDetail.csat_rating ? 'Update your rating' : 'How did we do?'}</strong>
                  <div className="portal-csat-picker" role="radiogroup" aria-label="Rating from 1 to 5">
                    {[1, 2, 3, 4, 5].map((value) => (
                      <button
                        type="button"
                        key={value}
                        role="radio"
                        aria-checked={csatDraft.rating === value}
                        aria-label={`${value} star${value === 1 ? '' : 's'}`}
                        className={csatDraft.rating >= value ? 'active' : ''}
                        onClick={() => setCsatDraft((current) => ({ ...current, rating: value }))}
                      >
                        <Star size={20} />
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={csatDraft.comment}
                    onChange={(event) =>
                      setCsatDraft((current) => ({ ...current, comment: event.target.value }))
                    }
                    placeholder="Anything we should know? (optional)"
                    rows={2}
                    maxLength={1000}
                  />
                  <button
                    className="primary-action portal-submit"
                    type="submit"
                    disabled={csatBusy || csatDraft.rating < 1}
                  >
                    {csatBusy ? <RefreshCw size={16} className="spin-icon" /> : <Star size={16} />}
                    Submit rating
                  </button>
                </form>
              </div>
            ) : null}
          </section>
        </div>

        <form className="portal-panel portal-ticket-form" onSubmit={submitTicket}>
          <div className="portal-section-head">
            <div>
              <span>Support ticket</span>
              <h2>Send the request</h2>
            </div>
            <Send size={20} />
          </div>
          {notice ? <strong className="portal-notice">{notice}</strong> : null}
          <div className="portal-form-grid">
            <label>
              Name
              <input
                value={draft.name}
                onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                autoComplete="name"
                required
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={draft.email}
                onChange={(event) => setDraft((current) => ({ ...current, email: event.target.value }))}
                autoComplete="email"
                required
              />
            </label>
            <label>
              Phone
              <input
                value={draft.phone}
                onChange={(event) => setDraft((current) => ({ ...current, phone: event.target.value }))}
                autoComplete="tel"
              />
            </label>
            <label>
              Priority
              <select
                value={draft.priority}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    priority: event.target.value as typeof current.priority,
                  }))
                }
              >
                {priorityOptions.map((priority) => (
                  <option key={priority} value={priority}>{titleCase(priority)}</option>
                ))}
              </select>
            </label>
            <label className="span-all">
              Subject
              <input
                value={draft.subject}
                onChange={(event) => setDraft((current) => ({ ...current, subject: event.target.value }))}
                required
              />
            </label>
            <label className="span-all">
              Details
              <textarea
                value={draft.description}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, description: event.target.value }))
                }
                required
              />
            </label>
            <label className="span-all portal-file-field">
              Attach proof
              <input type="file" onChange={(event) => setAttachmentFile(event.target.files?.[0] ?? null)} />
              {attachmentFile ? (
                <small>{attachmentFile.name} / {formatFileSize(attachmentFile.size)}</small>
              ) : null}
            </label>
          </div>
          {ticketFields.length ? (
            <div className="portal-custom-fields" aria-label="Ticket details">
              {ticketFields.map((field) => (
                <label className={field.field_type === 'textarea' ? 'span-all' : ''} key={field.id}>
                  <span>
                    {field.label}
                    {field.required ? <em>Required</em> : null}
                  </span>
                  {renderFieldInput(field)}
                  {field.help_text ? <small>{field.help_text}</small> : null}
                </label>
              ))}
            </div>
          ) : null}
          <button className="primary-action portal-submit" type="submit" disabled={submitting}>
            {submitting ? <RefreshCw size={16} className="spin-icon" /> : <Send size={16} />}
            Submit ticket
          </button>
        </form>
      </section>
    </main>
  )
}

export default PortalHelpCenter
