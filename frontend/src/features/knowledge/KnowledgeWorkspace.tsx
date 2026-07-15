import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BookOpen,
  Bot,
  ExternalLink,
  Inbox,
  LayoutDashboard,
  LoaderCircle,
  MessageSquareReply,
  Plus,
  Search,
  Settings,
  Users,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import type { BackendSession } from '../../backend'
import {
  createKnowledge,
  fetchKnowledge,
  updateKnowledge,
  type KnowledgeArticle,
} from './api'
import './knowledge-workspace.css'

interface KnowledgeWorkspaceProps {
  session: BackendSession
  online: boolean
  onNavigate: (screen: string) => void
  onSignOut: () => void
}

const statuses: KnowledgeArticle['status'][] = [
  'draft',
  'in_review',
  'approved',
  'published',
  'archived',
]

function initials(value: string) {
  return value.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()
}

function readable(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function categoryFor(article: KnowledgeArticle) {
  return article.tags?.[0]?.trim() || 'General'
}

export function KnowledgeWorkspace({
  session,
  online,
  onNavigate,
  onSignOut,
}: KnowledgeWorkspaceProps) {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('en')
  const [manage, setManage] = useState(false)
  const [selected, setSelected] = useState<KnowledgeArticle | null>(null)
  const [newOpen, setNewOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState({ title: '', category: 'General', body: '', language: 'en' })

  const knowledgeQuery = useQuery({
    queryKey: ['knowledge-workspace', session.market.id],
    queryFn: () => fetchKnowledge(session),
  })

  const articles = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return (knowledgeQuery.data ?? []).filter((article) => {
      if (language && article.language !== language) return false
      if (!normalized) return true
      return [article.title, article.body, ...(article.tags ?? [])]
        .join(' ')
        .toLowerCase()
        .includes(normalized)
    })
  }, [knowledgeQuery.data, language, query])

  const categories = useMemo(() => {
    const grouped = new Map<string, KnowledgeArticle[]>()
    for (const article of articles) {
      const category = categoryFor(article)
      grouped.set(category, [...(grouped.get(category) ?? []), article])
    }
    return [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right))
  }, [articles])

  const createMutation = useMutation({
    mutationFn: () =>
      createKnowledge(session, {
        title: draft.title.trim(),
        body: draft.body.trim(),
        language: draft.language,
        status: 'draft',
        tags: [draft.category.trim() || 'General'],
        channels: [],
        market_ids: [session.market.id],
      }),
    onSuccess: () => {
      setNewOpen(false)
      setDraft({ title: '', category: 'General', body: '', language })
      setNotice('Draft article created.')
      void queryClient.invalidateQueries({ queryKey: ['knowledge-workspace', session.market.id] })
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Article creation failed.'),
  })

  const statusMutation = useMutation({
    mutationFn: ({ article, status }: { article: KnowledgeArticle; status: KnowledgeArticle['status'] }) =>
      updateKnowledge(session, article.id, { status }),
    onSuccess: (article) => {
      setSelected((current) => current?.id === article.id ? article : current)
      setNotice(`Article moved to ${readable(article.status)}.`)
      void queryClient.invalidateQueries({ queryKey: ['knowledge-workspace', session.market.id] })
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Article update failed.'),
  })

  return (
    <div className="knowledge-shell">
      <aside className="knowledge-rail" aria-label="Knowledge navigation">
        <button className="knowledge-logo" type="button" onClick={() => onNavigate('command')} title="Omni home">O</button>
        <nav>
          <button type="button" title="Dashboard" aria-label="Dashboard" onClick={() => onNavigate('command')}><LayoutDashboard size={19} /></button>
          <button type="button" title="Tickets" aria-label="Tickets" onClick={() => onNavigate('inbox')}><Inbox size={19} /></button>
          <button type="button" title="Omnichat" aria-label="Omnichat" onClick={() => onNavigate('channels')}><MessageSquareReply size={19} /></button>
          <button type="button" title="Contacts" aria-label="Contacts" onClick={() => onNavigate('customers')}><Users size={19} /></button>
          <button className="active" type="button" title="Solutions" aria-label="Solutions"><BookOpen size={19} /></button>
          <button type="button" title="AI Agents" aria-label="AI Agents" onClick={() => onNavigate('automation')}><Bot size={19} /></button>
        </nav>
        <div className="knowledge-rail-bottom">
          <span className={`knowledge-online ${online ? 'connected' : ''}`} title={online ? 'Online' : 'Offline'} />
          <button type="button" title="Admin" aria-label="Admin" onClick={() => onNavigate('admin')}><Settings size={19} /></button>
          <button type="button" className="knowledge-user" title={session.user.name} aria-label={session.user.name}>{initials(session.user.name)}</button>
        </div>
      </aside>

      <main className="knowledge-main">
        <header className="knowledge-head">
          <h1>Knowledge base (Wakanow)</h1>
          <div>
            <button type="button" className={manage ? 'active' : ''} aria-pressed={manage} onClick={() => setManage((current) => !current)}><Settings size={15} /> Manage</button>
            <button type="button" className="primary" onClick={() => setNewOpen(true)}><Plus size={16} /> New article</button>
            <select aria-label="Knowledge language" value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">EN</option><option value="fr">FR</option><option value="pt">PT</option><option value="ar">AR</option></select>
            <a className="knowledge-icon-link" aria-label="View support portal" title="View support portal" href={`/?screen=portal&market=${session.market.code}`} target="_blank" rel="noreferrer"><ExternalLink size={16} /></a>
          </div>
        </header>

        <section className="knowledge-toolbar" aria-label="Knowledge controls">
          <label><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search articles" aria-label="Search articles" /></label>
          <span>{articles.length} article{articles.length === 1 ? '' : 's'}</span>
        </section>

        <section className="knowledge-grid" aria-label="Knowledge categories">
          {knowledgeQuery.isLoading ? <div className="knowledge-state"><LoaderCircle className="spin" size={20} /> Loading knowledge</div> : null}
          {knowledgeQuery.isError ? <div className="knowledge-state error">{knowledgeQuery.error.message}</div> : null}
          {!knowledgeQuery.isLoading && !categories.length ? <div className="knowledge-state"><BookOpen size={26} /><strong>No articles match this view</strong></div> : null}
          {categories.map(([category, items]) => (
            <article className="knowledge-category" key={category}>
              <header><BookOpen size={18} /><h2>{category}</h2><span>{items.length}</span></header>
              <div>
                {items.slice(0, 4).map((article) => (
                  <div className="knowledge-article-row" key={article.id}>
                    <button type="button" onClick={() => setSelected(article)}><span>{article.title}</span><small>{readable(article.status)}</small></button>
                    {manage ? <select aria-label={`Status for ${article.title}`} value={article.status} onChange={(event) => statusMutation.mutate({ article, status: event.target.value as KnowledgeArticle['status'] })}>{statuses.map((status) => <option value={status} key={status}>{readable(status)}</option>)}</select> : null}
                  </div>
                ))}
              </div>
              {items.length > 4 ? <button className="knowledge-view-all" type="button" onClick={() => setQuery(category)}>View all {items.length} articles</button> : null}
            </article>
          ))}
        </section>

        <footer className="knowledge-footer"><span>{session.market.code} · {session.market.name}</span><button type="button" onClick={onSignOut}>Sign out</button></footer>
      </main>

      {notice ? <div className="knowledge-toast" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Dismiss"><X size={14} /></button></div> : null}
      {selected ? <div className="knowledge-dialog-backdrop" role="presentation"><section className="knowledge-dialog article" role="dialog" aria-modal="true" aria-labelledby="knowledge-article-title"><header><div><span>{categoryFor(selected)}</span><h2 id="knowledge-article-title">{selected.title}</h2></div><button type="button" onClick={() => setSelected(null)} aria-label="Close"><X size={18} /></button></header><p>{selected.body}</p><footer><label>Status<select value={selected.status} onChange={(event) => statusMutation.mutate({ article: selected, status: event.target.value as KnowledgeArticle['status'] })}>{statuses.map((status) => <option value={status} key={status}>{readable(status)}</option>)}</select></label><span>{selected.language.toUpperCase()}</span></footer></section></div> : null}
      {newOpen ? <div className="knowledge-dialog-backdrop" role="presentation"><form className="knowledge-dialog" onSubmit={(event) => { event.preventDefault(); createMutation.mutate() }}><header><div><span>NEW ARTICLE</span><h2>Create a knowledge article</h2></div><button type="button" onClick={() => setNewOpen(false)} aria-label="Close"><X size={18} /></button></header><label>Title<input required minLength={2} value={draft.title} onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} /></label><label>Category<input required value={draft.category} onChange={(event) => setDraft((current) => ({ ...current, category: event.target.value }))} /></label><label>Language<select value={draft.language} onChange={(event) => setDraft((current) => ({ ...current, language: event.target.value }))}><option value="en">English</option><option value="fr">French</option><option value="pt">Portuguese</option><option value="ar">Arabic</option></select></label><label>Body<textarea required value={draft.body} onChange={(event) => setDraft((current) => ({ ...current, body: event.target.value }))} /></label><footer><button type="button" onClick={() => setNewOpen(false)}>Cancel</button><button type="submit" className="primary" disabled={createMutation.isPending}>Create draft</button></footer></form></div> : null}
    </div>
  )
}

export default KnowledgeWorkspace
