import type { BackendSession } from '../../backend'
import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'

export type KnowledgeArticle = components['schemas']['KnowledgeArticle']
export type CreateKnowledgeArticle = components['schemas']['CreateKnowledgeArticleRequest']
export type UpdateKnowledgeArticle = components['schemas']['UpdateKnowledgeArticleRequest']

function apiError(error: unknown) {
  if (typeof error === 'object' && error && 'detail' in error) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === 'string') return new Error(detail)
  }
  return new Error('The knowledge request could not be completed.')
}

export async function fetchKnowledge(session: BackendSession): Promise<KnowledgeArticle[]> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.GET('/api/v1/knowledge')
  if (error || !data) throw apiError(error)
  return data
}

export async function createKnowledge(
  session: BackendSession,
  payload: CreateKnowledgeArticle,
): Promise<KnowledgeArticle> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.POST('/api/v1/knowledge', { body: payload })
  if (error || !data) throw apiError(error)
  return data
}

export async function updateKnowledge(
  session: BackendSession,
  articleId: string,
  payload: UpdateKnowledgeArticle,
): Promise<KnowledgeArticle> {
  const client = createOmniApiClient(session)
  const { data, error } = await client.PATCH('/api/v1/knowledge/{article_id}', {
    params: { path: { article_id: articleId } },
    body: payload,
  })
  if (error || !data) throw apiError(error)
  return data
}
