import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { BackendSession } from '../../backend'
import {
  isRealtimeEnvelope,
  OmniRealtimeClient,
  type RealtimeConnectionStatus,
  type RealtimeEnvelope,
} from '../../api/realtime'

export interface RealtimeActorActivity {
  userId: string
  userName: string
  timestamp: string
  messageId?: string
}

interface UseOmnichatRealtimeOptions {
  session: BackendSession | null
  online: boolean
  onDurableEvent: (event: RealtimeEnvelope) => void
}

type ActivityIndex = Record<string, Record<string, RealtimeActorActivity>>

function actorActivity(event: RealtimeEnvelope): RealtimeActorActivity | null {
  const userId = typeof event.payload.user_id === 'string' ? event.payload.user_id : ''
  if (!userId) return null
  return {
    userId,
    userName:
      typeof event.payload.user_name === 'string' && event.payload.user_name.trim()
        ? event.payload.user_name
        : 'Team member',
    timestamp: event.timestamp,
    messageId:
      typeof event.payload.message_id === 'string' ? event.payload.message_id : undefined,
  }
}

function activityArrays(index: ActivityIndex): Record<string, RealtimeActorActivity[]> {
  return Object.fromEntries(
    Object.entries(index).map(([aggregateId, actors]) => [aggregateId, Object.values(actors)]),
  )
}

export function useOmnichatRealtime({
  session,
  online,
  onDurableEvent,
}: UseOmnichatRealtimeOptions) {
  const clientRef = useRef<OmniRealtimeClient | null>(null)
  const onDurableEventRef = useRef(onDurableEvent)
  const typingExpiryRef = useRef(new Map<string, number>())
  const lastReadSentRef = useRef(new Map<string, string>())
  const [connectionStatus, setConnectionStatus] =
    useState<RealtimeConnectionStatus>('disconnected')
  const [typingIndex, setTypingIndex] = useState<ActivityIndex>({})
  const [readIndex, setReadIndex] = useState<ActivityIndex>({})
  const [presenceIndex, setPresenceIndex] = useState<ActivityIndex>({})

  useEffect(() => {
    onDurableEventRef.current = onDurableEvent
  }, [onDurableEvent])

  useEffect(() => {
    if (!session || !online) {
      return
    }

    const client = new OmniRealtimeClient(
      session,
      (message) => {
        if (!isRealtimeEnvelope(message)) return
        const actor = actorActivity(message)

        if (message.type === 'typing.updated' && actor) {
          const typing = message.payload.typing === true
          const timerKey = `${message.aggregate_id}:${actor.userId}`
          const previousTimer = typingExpiryRef.current.get(timerKey)
          if (previousTimer !== undefined) window.clearTimeout(previousTimer)

          setTypingIndex((current) => {
            const conversation = { ...(current[message.aggregate_id] ?? {}) }
            if (typing) conversation[actor.userId] = actor
            else delete conversation[actor.userId]
            return { ...current, [message.aggregate_id]: conversation }
          })

          if (typing) {
            const timer = window.setTimeout(() => {
              setTypingIndex((current) => {
                const conversation = { ...(current[message.aggregate_id] ?? {}) }
                delete conversation[actor.userId]
                return { ...current, [message.aggregate_id]: conversation }
              })
              typingExpiryRef.current.delete(timerKey)
            }, 5_000)
            typingExpiryRef.current.set(timerKey, timer)
          } else {
            typingExpiryRef.current.delete(timerKey)
          }
        } else if (message.type === 'message.read' && actor) {
          setReadIndex((current) => ({
            ...current,
            [message.aggregate_id]: {
              ...(current[message.aggregate_id] ?? {}),
              [actor.userId]: actor,
            },
          }))
        } else if (message.type === 'presence.updated' && actor) {
          setPresenceIndex((current) => {
            const marketPresence = { ...(current[message.market_id] ?? {}) }
            if (message.payload.online === false) delete marketPresence[actor.userId]
            else marketPresence[actor.userId] = actor
            return { ...current, [message.market_id]: marketPresence }
          })
        }

        if (!message.event_id.startsWith('ephemeral_')) {
          onDurableEventRef.current(message)
        }
      },
      setConnectionStatus,
    )
    clientRef.current = client
    client.start()

    const typingTimers = typingExpiryRef.current
    return () => {
      client.stop()
      clientRef.current = null
      for (const timer of typingTimers.values()) window.clearTimeout(timer)
      typingTimers.clear()
      setTypingIndex({})
      setPresenceIndex({})
    }
  }, [online, session])

  const sendTyping = useCallback(
    (conversationId: string, typing: boolean) =>
      clientRef.current?.send('typing.updated', conversationId, { typing }) ?? false,
    [],
  )

  const markRead = useCallback((conversationId: string, messageId: string) => {
    if (!conversationId || !messageId) return false
    if (lastReadSentRef.current.get(conversationId) === messageId) return true
    const sent =
      clientRef.current?.send('message.read', conversationId, { message_id: messageId }) ?? false
    if (sent) lastReadSentRef.current.set(conversationId, messageId)
    return sent
  }, [])

  return {
    connectionStatus,
    typingByConversation: useMemo(() => activityArrays(typingIndex), [typingIndex]),
    readsByConversation: useMemo(() => activityArrays(readIndex), [readIndex]),
    presenceByMarket: useMemo(() => activityArrays(presenceIndex), [presenceIndex]),
    sendTyping,
    markRead,
  }
}
