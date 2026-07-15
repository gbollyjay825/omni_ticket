import createClient from 'openapi-fetch'

import { getBackendBaseUrl } from '../backend'
import type { paths } from './schema'

export interface ApiClientSession {
  access_token: string
  market: { id: string }
}

export function createOmniApiClient(session?: ApiClientSession | null) {
  const headers: Record<string, string> = {}
  if (session) {
    headers['X-Omni-Market'] = session.market.id
    if (session.access_token) headers.Authorization = `Bearer ${session.access_token}`
  }
  const configuredBaseUrl = getBackendBaseUrl()
  const baseUrl = configuredBaseUrl.endsWith('/api/v1')
    ? configuredBaseUrl.slice(0, -'/api/v1'.length)
    : configuredBaseUrl
  return createClient<paths>({
    baseUrl,
    credentials: 'include',
    headers: Object.keys(headers).length ? headers : undefined,
  })
}
