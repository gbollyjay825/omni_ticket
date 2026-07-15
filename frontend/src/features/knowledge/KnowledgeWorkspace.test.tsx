import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { BackendSession } from '../../backend'
import type { KnowledgeArticle } from './api'
import { KnowledgeWorkspace } from './KnowledgeWorkspace'

const api = vi.hoisted(() => ({
  createKnowledge: vi.fn(),
  fetchKnowledge: vi.fn(),
  updateKnowledge: vi.fn(),
}))

vi.mock('./api', () => api)

const article = {
  id: 'article-1',
  title: 'Changing a flight booking',
  body: 'Confirm fare rules before changing the booking.',
  language: 'en',
  status: 'published',
  tags: ['Flight Reservations'],
  channels: ['email'],
  market_ids: ['market-ng'],
  owner: 'Knowledge Team',
  created_at: '2026-07-14T12:00:00Z',
  updated_at: '2026-07-14T12:00:00Z',
} as unknown as KnowledgeArticle

const session = {
  access_token: 'test-token',
  token_type: 'bearer',
  market: {
    id: 'market-ng',
    code: 'NG',
    name: 'Nigeria',
    timezone: 'Africa/Lagos',
    currency: 'NGN',
    default_locale: 'en-NG',
    support_email: 'support@wakanow.com',
  },
  available_markets: [],
  user: {
    id: 'user-admin',
    name: 'Gbolahan Salami',
    email: 'gbolahan@wakanow.com',
    role: 'admin',
    market_ids: ['market-ng'],
    default_market_id: 'market-ng',
    active: true,
  },
} as unknown as BackendSession

function renderWorkspace() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <KnowledgeWorkspace session={session} online onNavigate={vi.fn()} onSignOut={vi.fn()} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  api.fetchKnowledge.mockResolvedValue([article])
  api.createKnowledge.mockResolvedValue({ ...article, id: 'article-2', title: 'Refund timelines', status: 'draft' })
  api.updateKnowledge.mockResolvedValue({ ...article, status: 'archived' })
})

describe('KnowledgeWorkspace', () => {
  it('groups API articles into a Freshdesk-style category catalog', async () => {
    renderWorkspace()

    expect(screen.getByRole('heading', { name: 'Knowledge base (Wakanow)' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Flight Reservations' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Changing a flight booking/ })).toBeInTheDocument()
    expect(api.fetchKnowledge).toHaveBeenCalledWith(session)
  })

  it('filters the catalog without fabricating results', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await screen.findByText('Changing a flight booking')
    await user.type(screen.getByRole('textbox', { name: 'Search articles' }), 'hotel')

    expect(screen.getByText('No articles match this view')).toBeInTheDocument()
  })

  it('creates a draft through the knowledge API', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await user.click(await screen.findByRole('button', { name: 'New article' }))
    await user.type(screen.getByLabelText('Title'), 'Refund timelines')
    await user.clear(screen.getByLabelText('Category'))
    await user.type(screen.getByLabelText('Category'), 'Refunds')
    await user.type(screen.getByLabelText('Body'), 'Explain each refund processing stage.')
    await user.click(screen.getByRole('button', { name: 'Create draft' }))

    await waitFor(() => expect(api.createKnowledge).toHaveBeenCalledTimes(1))
    expect(api.createKnowledge).toHaveBeenCalledWith(session, {
      title: 'Refund timelines',
      body: 'Explain each refund processing stage.',
      language: 'en',
      status: 'draft',
      tags: ['Refunds'],
      channels: [],
      market_ids: ['market-ng'],
    })
  })

  it('updates article status through Manage mode', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await user.click(await screen.findByRole('button', { name: 'Manage' }))
    await user.selectOptions(screen.getByRole('combobox', { name: `Status for ${article.title}` }), 'archived')

    await waitFor(() => expect(api.updateKnowledge).toHaveBeenCalledTimes(1))
    expect(api.updateKnowledge).toHaveBeenCalledWith(session, article.id, { status: 'archived' })
  })
})
