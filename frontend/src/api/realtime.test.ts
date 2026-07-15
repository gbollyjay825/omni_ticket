import { describe, expect, it } from 'vitest'

import { buildRealtimeUrl } from './realtime'

describe('buildRealtimeUrl', () => {
  it('resolves the production relative API base against the page origin', () => {
    const url = buildRealtimeUrl('/api/v1', 'market-ng', null, 'https://omni.wakanow.com')

    expect(url.toString()).toBe(
      'wss://omni.wakanow.com/api/v1/realtime?market_id=market-ng',
    )
  })

  it('preserves an absolute development API host and durable cursor', () => {
    const url = buildRealtimeUrl(
      'http://127.0.0.1:8000/api/v1/',
      'market-ng',
      'event-42',
      'https://omni.wakanow.com',
    )

    expect(url.toString()).toBe(
      'ws://127.0.0.1:8000/api/v1/realtime?market_id=market-ng&cursor=event-42',
    )
  })
})
