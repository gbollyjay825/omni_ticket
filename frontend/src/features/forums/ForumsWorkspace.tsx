import { useMemo, useState } from 'react'
import { ChevronDown, MessageSquare, MoreHorizontal, Plus, Search, Star, X } from 'lucide-react'
import type { BackendDiscussionComment } from '../../backend'
import type { DiscussionTopic } from '../../domain'
import './forums-workspace.css'

interface TopicInput {
  title: string
  category?: string
  body?: string
  status?: string
  pinned?: boolean
}

interface ForumsWorkspaceProps {
  topics: DiscussionTopic[]
  currentUser: string
  onCreate: (input: TopicInput) => Promise<boolean>
  onUpdate: (topicId: string, input: Partial<TopicInput>) => Promise<boolean>
  onLoadComments: (topicId: string) => Promise<BackendDiscussionComment[]>
  onReply: (topicId: string, body: string) => Promise<void>
}

type ForumView = 'all' | 'mine' | 'waiting' | 'spam'

function timeAgo(value: string) {
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) return value
  const minutes = Math.max(0, Math.round((Date.now() - timestamp) / 60000))
  if (minutes < 1) return 'now'
  if (minutes < 60) return `${minutes} minutes ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hours ago`
  const days = Math.round(hours / 24)
  if (days < 365) return `${days} days ago`
  return `${Math.round(days / 365)} years ago`
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'O'
}

export function ForumsWorkspace({ topics, currentUser, onCreate, onUpdate, onLoadComments, onReply }: ForumsWorkspaceProps) {
  const [view, setView] = useState<ForumView>('all')
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [newTopicOpen, setNewTopicOpen] = useState(false)
  const [draft, setDraft] = useState({ title: '', category: 'Announcements', body: '' })
  const [selectedId, setSelectedId] = useState('')
  const [comments, setComments] = useState<BackendDiscussionComment[]>([])
  const [commentDraft, setCommentDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const categories = useMemo(() => {
    const counts = new Map<string, number>()
    topics.forEach((topic) => counts.set(topic.category || 'General', (counts.get(topic.category || 'General') ?? 0) + 1))
    return [...counts.entries()].sort(([left], [right]) => left.localeCompare(right))
  }, [topics])

  const visibleTopics = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return [...topics]
      .filter((topic) => category === 'all' || topic.category === category)
      .filter((topic) => view !== 'mine' || topic.author.toLowerCase() === currentUser.toLowerCase())
      .filter((topic) => view !== 'waiting' || topic.status === 'pending')
      .filter((topic) => view !== 'spam' || topic.status === 'spam')
      .filter((topic) => !needle || `${topic.title} ${topic.body} ${topic.author} ${topic.category}`.toLowerCase().includes(needle))
      .sort((left, right) => Number(right.pinned) - Number(left.pinned) || new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime())
  }, [category, currentUser, search, topics, view])

  const selectedTopic = topics.find((topic) => topic.id === selectedId)

  async function openTopic(topic: DiscussionTopic) {
    setSelectedId(topic.id)
    setError('')
    setComments([])
    setBusy(true)
    try {
      setComments(await onLoadComments(topic.id))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Replies could not be loaded.')
    } finally {
      setBusy(false)
    }
  }

  async function createTopic() {
    setBusy(true)
    setError('')
    try {
      if (await onCreate({ title: draft.title.trim(), category: draft.category.trim(), body: draft.body.trim() })) {
        setDraft({ title: '', category: 'Announcements', body: '' })
        setNewTopicOpen(false)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The topic could not be created.')
    } finally {
      setBusy(false)
    }
  }

  async function updateTopic(topic: DiscussionTopic, input: Partial<TopicInput>) {
    setBusy(true)
    setError('')
    try {
      await onUpdate(topic.id, input)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The topic could not be updated.')
    } finally {
      setBusy(false)
    }
  }

  async function addReply() {
    if (!selectedTopic || !commentDraft.trim()) return
    setBusy(true)
    setError('')
    try {
      await onReply(selectedTopic.id, commentDraft.trim())
      setComments(await onLoadComments(selectedTopic.id))
      setCommentDraft('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The reply could not be posted.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="forums-workspace" aria-label="Forums workspace">
      <aside aria-label="Forum views and categories">
        <h2>Views and Categories</h2>
        <nav aria-label="Forum views">
          {[
            ['all', 'All Activity'],
            ['mine', 'Your Topics Activity'],
            ['waiting', 'Waiting for Approval'],
            ['spam', 'Spam'],
          ].map(([id, label]) => <button key={id} type="button" className={view === id ? 'active' : ''} onClick={() => setView(id as ForumView)}><span>−</span>{label}</button>)}
        </nav>
        <button type="button" className={category === 'all' ? 'category-active' : ''} onClick={() => setCategory('all')}><span>−</span>All Categories</button>
        <div className="forum-category-title"><ChevronDown size={14} /><strong>Wakanow Forums</strong></div>
        <div className="forum-category-list">
          {categories.map(([name, count]) => <button key={name} type="button" className={category === name ? 'active' : ''} onClick={() => setCategory(name)}>− <span>{name}</span> <small>({count})</small></button>)}
        </div>
      </aside>

      <main>
        <header className="forums-commandbar">
          <div role="tablist" aria-label="Forum activity tabs">
            <button type="button" role="tab" aria-selected={view === 'all'} onClick={() => setView('all')}>All Activity</button>
            <button type="button" role="tab" aria-selected={view === 'mine'} onClick={() => setView('mine')}>Your Topics Activity</button>
          </div>
          <label><Search size={15} /><input aria-label="Search forum topics" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search topics" /></label>
          <button type="button" className="primary-action" onClick={() => setNewTopicOpen(true)}><Plus size={15} /> New topic</button>
        </header>

        {error ? <p className="forum-error" role="alert">{error}</p> : null}
        {selectedTopic ? (
          <article className="forum-topic-detail">
            <header><button type="button" onClick={() => setSelectedId('')}>All activity</button><span>/</span><strong>{selectedTopic.title}</strong><button type="button" className="icon-button" aria-label="Close topic" onClick={() => setSelectedId('')}><X size={16} /></button></header>
            <div className="forum-detail-body"><div className="forum-avatar">{initials(selectedTopic.author)}</div><div><span>{selectedTopic.category}</span><h3>{selectedTopic.title}</h3><p>{selectedTopic.body || 'No topic description was provided.'}</p><small>{selectedTopic.author} · {timeAgo(selectedTopic.updatedAt)}</small></div></div>
            <div className="forum-detail-actions">
              <button type="button" onClick={() => void updateTopic(selectedTopic, { pinned: !selectedTopic.pinned })}><Star size={14} /> {selectedTopic.pinned ? 'Unpin' : 'Pin'}</button>
              <label>Status <select value={selectedTopic.status} onChange={(event) => void updateTopic(selectedTopic, { status: event.target.value })} disabled={busy}><option value="open">Open</option><option value="answered">Answered</option><option value="closed">Closed</option><option value="pending">Waiting for approval</option><option value="spam">Spam</option></select></label>
            </div>
            <div className="forum-replies">
              {busy && comments.length === 0 ? <p>Loading replies…</p> : comments.map((comment) => <article key={comment.id}><div className="forum-avatar">{initials(comment.author)}</div><div><strong>{comment.author}</strong><span>{timeAgo(comment.created_at)}</span><p>{comment.body}</p></div></article>)}
              {!busy && comments.length === 0 ? <p>No replies yet.</p> : null}
            </div>
            <form onSubmit={(event) => { event.preventDefault(); void addReply() }}><textarea aria-label="Reply to topic" rows={3} value={commentDraft} onChange={(event) => setCommentDraft(event.target.value)} placeholder="Write a reply" /><button type="submit" className="primary-action" disabled={busy || !commentDraft.trim()}>Post reply</button></form>
          </article>
        ) : (
          <div className="forum-activity-list" aria-live="polite">
            {visibleTopics.map((topic) => (
              <article key={topic.id}>
                <div className="forum-avatar">{initials(topic.author)}</div>
                <div><span className={topic.replyCount ? 'reply' : 'new'}>{topic.replyCount ? 'Reply' : 'New Topic'}</span><small>{timeAgo(topic.updatedAt)}, In {topic.category}</small><button type="button" onClick={() => void openTopic(topic)}><strong>{topic.author}</strong> {topic.replyCount ? 'replied to topic' : 'created a topic'} {topic.title}</button><p>{topic.body}</p></div>
                {topic.pinned ? <Star size={15} aria-label="Pinned topic" /> : <button type="button" className="icon-button" aria-label={`More actions for ${topic.title}`}><MoreHorizontal size={16} /></button>}
              </article>
            ))}
            {visibleTopics.length === 0 ? <div className="forum-empty"><MessageSquare size={30} /><strong>No matching forum activity</strong><span>Change the view, category, or search.</span></div> : null}
          </div>
        )}
      </main>

      {newTopicOpen ? <div className="forum-modal-backdrop" role="presentation" onMouseDown={() => setNewTopicOpen(false)}><form className="forum-topic-dialog" aria-label="New forum topic" onSubmit={(event) => { event.preventDefault(); void createTopic() }} onMouseDown={(event) => event.stopPropagation()}><header><div><span>Wakanow Forums</span><h3>New topic</h3></div><button type="button" className="icon-button" aria-label="Close new topic" onClick={() => setNewTopicOpen(false)}><X size={16} /></button></header><div><label><span>Title</span><input required value={draft.title} onChange={(event) => setDraft((value) => ({ ...value, title: event.target.value }))} /></label><label><span>Category</span><input required value={draft.category} onChange={(event) => setDraft((value) => ({ ...value, category: event.target.value }))} /></label><label><span>Description</span><textarea rows={6} value={draft.body} onChange={(event) => setDraft((value) => ({ ...value, body: event.target.value }))} /></label></div><footer><button type="button" onClick={() => setNewTopicOpen(false)}>Cancel</button><button type="submit" className="primary-action" disabled={busy || !draft.title.trim()}>Create topic</button></footer></form></div> : null}
    </section>
  )
}
