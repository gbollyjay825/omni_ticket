import { getBackendBaseUrl } from '../backend'
import type { BackendSession } from '../backend'

export interface RealtimeEnvelope {
  event_id: string
  type: string
  organization_id: string
  market_id: string
  aggregate_type: string
  aggregate_id: string
  version: number
  timestamp: string
  payload: Record<string, unknown>
}

export type RealtimeMessage = RealtimeEnvelope | { type: string; [key: string]: unknown }
export type RealtimeConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected'

export function isRealtimeEnvelope(message: RealtimeMessage): message is RealtimeEnvelope {
  return (
    typeof (message as Partial<RealtimeEnvelope>).event_id === 'string' &&
    typeof (message as Partial<RealtimeEnvelope>).aggregate_id === 'string'
  )
}

function durableCursor(value: unknown): string | null {
  return typeof value === 'string' && value && !value.startsWith('ephemeral_') ? value : null
}

export function buildRealtimeUrl(
  apiBaseUrl: string,
  marketId: string,
  cursor: string | null = null,
  pageOrigin = typeof window !== 'undefined' ? window.location.origin : undefined,
) {
  const url = new URL(apiBaseUrl, pageOrigin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `${url.pathname.replace(/\/$/, '')}/realtime`
  url.searchParams.set('market_id', marketId)
  if (cursor) url.searchParams.set('cursor', cursor)
  return url
}

export class OmniRealtimeClient {
  private socket: WebSocket | null = null
  private reconnectTimer: number | null = null
  private reconnectAttempts = 0
  private stopped = true
  private cursor: string | null = null
  private readonly seen = new Set<string>()
  private readonly session: BackendSession
  private readonly onMessage: (message: RealtimeMessage) => void
  private readonly onStatus?: (status: RealtimeConnectionStatus) => void

  constructor(
    session: BackendSession,
    onMessage: (message: RealtimeMessage) => void,
    onStatus?: (status: RealtimeConnectionStatus) => void,
  ) {
    this.session = session
    this.onMessage = onMessage
    this.onStatus = onStatus
  }

  start() {
    if (!this.stopped) return
    this.stopped = false
    this.onStatus?.('connecting')
    this.connect()
  }

  stop() {
    this.send('presence.updated', this.session.user.id, { online: false })
    this.stopped = true
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
    this.socket?.close(1000, 'Client stopped')
    this.socket = null
    this.onStatus?.('disconnected')
  }

  send(
    type: 'presence.updated' | 'typing.updated' | 'message.read',
    aggregateId: string,
    payload: Record<string, unknown> = {},
  ) {
    if (this.socket?.readyState !== WebSocket.OPEN) return false
    this.socket.send(JSON.stringify({ type, aggregate_id: aggregateId, payload }))
    return true
  }

  private connect() {
    if (this.stopped || typeof WebSocket === 'undefined') return
    let socket: WebSocket
    try {
      const url = buildRealtimeUrl(getBackendBaseUrl(), this.session.market.id, this.cursor)
      const protocols = ['omni.realtime.v1']
      if (this.session.access_token) protocols.push(`bearer.${this.session.access_token}`)
      socket = new WebSocket(url, protocols)
    } catch {
      this.scheduleReconnect()
      return
    }
    this.socket = socket
    this.socket.addEventListener('open', () => {
      this.reconnectAttempts = 0
      this.onStatus?.('connected')
      this.send('presence.updated', this.session.user.id, { online: true })
    })
    this.socket.addEventListener('message', (event) => this.handleMessage(event.data))
    this.socket.addEventListener('close', () => this.scheduleReconnect())
    this.socket.addEventListener('error', () => this.socket?.close())
  }

  private handleMessage(raw: unknown) {
    if (typeof raw !== 'string') return
    let message: RealtimeMessage
    try {
      message = JSON.parse(raw) as RealtimeMessage
    } catch {
      return
    }
    if (isRealtimeEnvelope(message)) {
      if (this.seen.has(message.event_id)) return
      this.seen.add(message.event_id)
      const cursor = durableCursor(message.event_id)
      if (cursor) this.cursor = cursor
      if (this.seen.size > 2_000) {
        const first = this.seen.values().next().value
        if (typeof first === 'string') this.seen.delete(first)
      }
    } else if (message.type === 'realtime.ready') {
      this.cursor = durableCursor(message.cursor)
    }
    this.onMessage(message)
  }

  private scheduleReconnect() {
    this.socket = null
    if (this.stopped) return
    this.onStatus?.('reconnecting')
    this.reconnectAttempts += 1
    const baseDelay = Math.min(30_000, 1_000 * 2 ** Math.min(this.reconnectAttempts - 1, 5))
    const delay = baseDelay + Math.floor(Math.random() * 500)
    this.reconnectTimer = window.setTimeout(() => this.connect(), delay)
  }
}
