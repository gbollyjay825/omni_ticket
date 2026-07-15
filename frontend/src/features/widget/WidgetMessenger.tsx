import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import { ArrowLeft, Circle, MessageCircle, RefreshCw, Send, X } from 'lucide-react'

import {
  createBackendWidgetConversation,
  createBackendWidgetMessage,
  fetchBackendWidgetConfiguration,
  fetchBackendWidgetConversation,
  type BackendWidgetConversation,
  type BackendWidgetPublicConfiguration,
} from '../../backend'
import './WidgetMessenger.css'

interface StoredWidgetConversation {
  publicId: string
  accessToken: string
}

function widgetMarket() {
  return new URLSearchParams(window.location.search).get('market')?.trim().toLowerCase() || 'ng'
}

function storedConversation(key: string): StoredWidgetConversation | null {
  try {
    const value = window.sessionStorage.getItem(key)
    if (!value) return null
    const parsed = JSON.parse(value) as Partial<StoredWidgetConversation>
    if (!parsed.publicId || !parsed.accessToken) return null
    return { publicId: parsed.publicId, accessToken: parsed.accessToken }
  } catch {
    return null
  }
}

function formatMessageTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(date)
}

export function WidgetMessenger() {
  const marketCode = widgetMarket()
  const storageKey = `omni-widget:${marketCode}:conversation`
  const [configuration, setConfiguration] = useState<BackendWidgetPublicConfiguration | null>(null)
  const [configurationError, setConfigurationError] = useState('')
  const [conversationSession, setConversationSession] = useState<StoredWidgetConversation | null>(
    () => storedConversation(storageKey),
  )
  const [conversation, setConversation] = useState<BackendWidgetConversation | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [openingMessage, setOpeningMessage] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const transcriptRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchBackendWidgetConfiguration(marketCode)
      .then((response) => {
        if (cancelled) return
        setConfiguration(response)
        setConfigurationError('')
      })
      .catch((fetchError) => {
        if (cancelled) return
        setConfigurationError(
          fetchError instanceof Error ? fetchError.message : 'Messenger configuration is unavailable.',
        )
      })
    return () => {
      cancelled = true
    }
  }, [marketCode])

  useEffect(() => {
    if (!conversationSession) return
    let cancelled = false

    const refresh = async (showProgress = false) => {
      if (document.visibilityState === 'hidden') return
      if (showProgress) setRefreshing(true)
      try {
        const response = await fetchBackendWidgetConversation(
          marketCode,
          conversationSession.publicId,
          conversationSession.accessToken,
        )
        if (cancelled) return
        setConversation(response)
        setError('')
      } catch (fetchError) {
        if (cancelled) return
        const detail = fetchError instanceof Error ? fetchError.message : 'Conversation refresh failed.'
        setError(detail)
        if (/invalid|expired/i.test(detail)) {
          window.sessionStorage.removeItem(storageKey)
          setConversationSession(null)
          setConversation(null)
        }
      } finally {
        if (!cancelled && showProgress) setRefreshing(false)
      }
    }

    void refresh(true)
    const timer = window.setInterval(() => void refresh(false), 3_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [conversationSession, marketCode, storageKey])

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: 'smooth' })
  }, [conversation?.messages.length])

  function closeWidget() {
    window.parent.postMessage({ type: 'omni-widget:close' }, '*')
  }

  function forgetConversation() {
    window.sessionStorage.removeItem(storageKey)
    setConversationSession(null)
    setConversation(null)
    setMessage('')
    setError('')
  }

  async function startConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || !configuration) return
    const body = openingMessage.trim()
    if (body.length < 2) return
    setBusy(true)
    setError('')
    try {
      const visitorIdKey = `omni-widget:${marketCode}:visitor`
      let visitorId = window.sessionStorage.getItem(visitorIdKey)
      if (!visitorId) {
        visitorId = window.crypto.randomUUID()
        window.sessionStorage.setItem(visitorIdKey, visitorId)
      }
      const response = await createBackendWidgetConversation(marketCode, {
        name: name.trim() || undefined,
        email: email.trim().toLowerCase() || undefined,
        message: body,
        visitor_id: visitorId,
      })
      if (!response.access_token) throw new Error('Messenger session token was not returned.')
      const session = { publicId: response.public_id, accessToken: response.access_token }
      window.sessionStorage.setItem(storageKey, JSON.stringify(session))
      setConversationSession(session)
      setConversation(response)
      setOpeningMessage('')
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : 'Conversation could not be started.')
    } finally {
      setBusy(false)
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || !conversationSession || !conversation) return
    const body = message.trim()
    if (!body) return
    setBusy(true)
    setError('')
    try {
      const response = await createBackendWidgetMessage(
        marketCode,
        conversation.public_id,
        conversationSession.accessToken,
        body,
      )
      setConversation(response)
      setMessage('')
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : 'Message could not be sent.')
    } finally {
      setBusy(false)
    }
  }

  const accent = configuration?.primary_color || '#0b5eea'
  const unavailable = configuration && !configuration.available

  return (
    <main className="widget-messenger" style={{ '--widget-accent': accent } as CSSProperties}>
      <header className="widget-messenger-header">
        <div className="widget-messenger-identity">
          <span className="widget-messenger-logo"><MessageCircle size={20} /></span>
          <span>
            <strong>{configuration?.display_name || 'Omni support'}</strong>
            <small>
              <Circle size={7} fill="currentColor" />
              {configuration?.available ? 'Online' : 'Leave a message'}
            </small>
          </span>
        </div>
        <button type="button" onClick={closeWidget} aria-label="Close messenger">
          <X size={18} />
        </button>
      </header>

      {configurationError ? (
        <section className="widget-messenger-state" role="alert">
          <MessageCircle size={28} />
          <strong>Messenger unavailable</strong>
          <p>{configurationError}</p>
        </section>
      ) : !configuration ? (
        <section className="widget-messenger-state" aria-busy="true">
          <RefreshCw size={24} className="spin-icon" />
          <strong>Connecting</strong>
        </section>
      ) : !configuration.enabled ? (
        <section className="widget-messenger-state">
          <MessageCircle size={28} />
          <strong>Messenger is not enabled</strong>
          <p>Use the Help Center or contact the market support team.</p>
        </section>
      ) : conversation ? (
        <>
          <div className="widget-conversation-bar">
            <span>
              <strong>{conversation.public_id}</strong>
              <small>{conversation.customer_status}</small>
            </span>
            <button type="button" onClick={forgetConversation} aria-label="Start a new conversation">
              <ArrowLeft size={15} />
              New
            </button>
          </div>
          <div className="widget-transcript" ref={transcriptRef} aria-live="polite">
            <div className="widget-welcome-message">
              <MessageCircle size={17} />
              <p>{configuration.welcome_message}</p>
            </div>
            {conversation.messages.map((item) => (
              <article className={`widget-message ${item.direction}`} key={item.id}>
                <div>
                  <strong>{item.direction === 'customer' ? 'You' : item.actor}</strong>
                  <time dateTime={item.created_at}>{formatMessageTime(item.created_at)}</time>
                </div>
                <p>{item.body}</p>
              </article>
            ))}
            {refreshing ? <small className="widget-refreshing">Checking for replies...</small> : null}
          </div>
          {error ? <p className="widget-error" role="alert">{error}</p> : null}
          <form className="widget-composer" onSubmit={sendMessage}>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Type a message"
              aria-label="Message"
              rows={2}
              maxLength={8000}
            />
            <button type="submit" disabled={busy || !message.trim()} aria-label="Send message">
              {busy ? <RefreshCw size={17} className="spin-icon" /> : <Send size={17} />}
            </button>
          </form>
        </>
      ) : (
        <section className="widget-start">
          <div className="widget-start-copy">
            <span className="widget-start-icon"><MessageCircle size={22} /></span>
            <strong>{configuration.welcome_message}</strong>
            {unavailable ? <p>{configuration.offline_message}</p> : <p>Send a message to start a conversation.</p>}
          </div>
          <form onSubmit={startConversation}>
            <label>
              Name
              <input value={name} onChange={(event) => setName(event.target.value)} maxLength={180} />
            </label>
            {configuration.collect_email ? (
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </label>
            ) : null}
            <label>
              How can we help?
              <textarea
                value={openingMessage}
                onChange={(event) => setOpeningMessage(event.target.value)}
                rows={4}
                minLength={2}
                maxLength={8000}
                required
              />
            </label>
            {error ? <p className="widget-error" role="alert">{error}</p> : null}
            <button className="widget-start-button" type="submit" disabled={busy}>
              {busy ? <RefreshCw size={17} className="spin-icon" /> : <Send size={17} />}
              Start conversation
            </button>
          </form>
        </section>
      )}
    </main>
  )
}

export default WidgetMessenger
