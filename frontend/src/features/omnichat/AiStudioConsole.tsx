import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Pause,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Settings,
  ShieldCheck,
} from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'

import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'
import type { BackendSession } from '../../backend'

type AiAgent = components['schemas']['AiAgentResponse']
type AiAgentPatch = components['schemas']['UpdateAiAgentRequest']
type AiDecision = components['schemas']['AiDecisionResponse']
type AiReadiness = components['schemas']['AiReadinessResponse']
type Channel = components['schemas']['ChannelType']

const aiChannels: Channel[] = [
  'email',
  'chat',
  'whatsapp',
  'facebook',
  'instagram',
  'sms',
  'portal',
]

const emptyDraft = {
  name: '',
  description: '',
  instructions: '',
  channels: ['email'] as Channel[],
  languages: 'en',
  handoffTeam: '',
  confidenceThreshold: 75,
  autoSend: false,
}

interface AiStudioConsoleProps {
  session: BackendSession | null
  canManage: boolean
  onOpenCredentials: () => void
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'detail' in error && typeof error.detail === 'string') {
    return error.detail
  }
  return 'AI Studio is unavailable.'
}

function splitLanguages(value: string) {
  return [...new Set(value.split(',').map((item) => item.trim().toLowerCase()).filter(Boolean))]
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function AiStudioConsole({
  session,
  canManage,
  onOpenCredentials,
}: AiStudioConsoleProps) {
  const client = useMemo(() => createOmniApiClient(session), [session])
  const queryClient = useQueryClient()
  const [view, setView] = useState<'agents' | 'decisions'>('agents')
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState(emptyDraft)

  const readinessQuery = useQuery({
    queryKey: ['ai-readiness', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<AiReadiness> => {
      const response = await client.GET('/api/v1/ai/readiness')
      if (response.error) throw response.error
      if (!response.data) throw new Error('AI readiness did not return data.')
      return response.data
    },
  })

  const agentsQuery = useQuery({
    queryKey: ['ai-agents', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<AiAgent[]> => {
      const response = await client.GET('/api/v1/ai/agents')
      if (response.error) throw response.error
      return response.data ?? []
    },
  })

  const decisionsQuery = useQuery({
    queryKey: ['ai-decisions', session?.market.id],
    enabled: Boolean(session) && view === 'decisions',
    queryFn: async (): Promise<AiDecision[]> => {
      const response = await client.GET('/api/v1/ai/decisions', {
        params: { query: { limit: 100 } },
      })
      if (response.error) throw response.error
      return response.data ?? []
    },
  })

  const refreshStudio = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['ai-agents', session?.market.id] }),
      queryClient.invalidateQueries({ queryKey: ['ai-readiness', session?.market.id] }),
      queryClient.invalidateQueries({ queryKey: ['ai-decisions', session?.market.id] }),
    ])
  }

  const createAgent = useMutation({
    mutationFn: async () => {
      const response = await client.POST('/api/v1/ai/agents', {
        body: {
          name: draft.name.trim(),
          description: draft.description.trim(),
          instructions: draft.instructions.trim(),
          channels: draft.channels,
          languages: splitLanguages(draft.languages),
          handoff_team: draft.handoffTeam.trim(),
          confidence_threshold: draft.confidenceThreshold,
          auto_send: draft.autoSend,
        },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (agent) => {
      await refreshStudio()
      closeForm()
      setNotice(`${agent?.name ?? 'AI agent'} saved as a draft.`)
    },
  })

  const updateAgent = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: AiAgentPatch }) => {
      const response = await client.PATCH('/api/v1/ai/agents/{agent_id}', {
        params: { path: { agent_id: id } },
        body,
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (agent) => {
      await refreshStudio()
      if (formOpen) closeForm()
      setNotice(`${agent?.name ?? 'AI agent'} is ${agent?.status ?? 'updated'}.`)
    },
  })

  const updatePolicy = useMutation({
    mutationFn: async (body: {
      automation_enabled?: boolean
      can_send_customer_messages?: boolean
    }) => {
      const response = await client.PATCH('/api/v1/ai/policy', { body })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async () => {
      await refreshStudio()
      setNotice('AI policy updated.')
    },
  })

  const readiness = readinessQuery.data
  const mutationError = createAgent.error ?? updateAgent.error ?? updatePolicy.error
  const queryError = readinessQuery.error ?? agentsQuery.error ?? decisionsQuery.error
  const busy = createAgent.isPending || updateAgent.isPending
  const canSubmit =
    canManage &&
    draft.name.trim().length >= 2 &&
    draft.instructions.trim().length >= 20 &&
    draft.channels.length > 0 &&
    splitLanguages(draft.languages).length > 0

  function closeForm() {
    setFormOpen(false)
    setEditingId(null)
    setDraft(emptyDraft)
  }

  function openCreateForm() {
    setEditingId(null)
    setDraft(emptyDraft)
    setFormOpen(true)
  }

  function openEditForm(agent: AiAgent) {
    setEditingId(agent.id)
    setDraft({
      name: agent.name,
      description: agent.description,
      instructions: agent.instructions,
      channels: agent.channels,
      languages: agent.languages.join(', '),
      handoffTeam: agent.handoff_team,
      confidenceThreshold: agent.confidence_threshold,
      autoSend: agent.auto_send,
    })
    setFormOpen(true)
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSubmit || busy) return
    if (editingId) {
      updateAgent.mutate({
        id: editingId,
        body: {
          name: draft.name.trim(),
          description: draft.description.trim(),
          instructions: draft.instructions.trim(),
          channels: draft.channels,
          languages: splitLanguages(draft.languages),
          handoff_team: draft.handoffTeam.trim(),
          confidence_threshold: draft.confidenceThreshold,
          auto_send: draft.autoSend,
        },
      })
    } else {
      createAgent.mutate()
    }
  }

  function toggleChannel(channel: Channel) {
    setDraft((current) => ({
      ...current,
      channels: current.channels.includes(channel)
        ? current.channels.filter((item) => item !== channel)
        : [...current.channels, channel],
    }))
  }

  if (queryError) {
    return (
      <div className="report-catalog-state error" role="alert">
        <AlertTriangle size={16} />
        <span>{errorMessage(queryError)}</span>
        <button
          type="button"
          onClick={() => {
            void readinessQuery.refetch()
            void agentsQuery.refetch()
            if (view === 'decisions') void decisionsQuery.refetch()
          }}
        >
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="ai-studio-console">
      <div className={`ai-readiness-banner ${readiness?.configured ? 'ready' : 'blocked'}`}>
        <span className="ai-readiness-icon">
          {readiness?.configured ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
        </span>
        <span>
          <strong>{readiness?.provider ?? 'Anthropic'} {readiness?.configured ? 'connected' : 'not configured'}</strong>
          <small>{readiness?.detail ?? 'Checking AI provider readiness...'}</small>
        </span>
        <span className="ai-model-chip">{readiness?.model ?? 'No model'}</span>
        {!readiness?.configured ? (
          <button type="button" onClick={onOpenCredentials}>
            <Settings size={14} />
            Configure
          </button>
        ) : null}
      </div>

      <div className="ai-policy-row" aria-label="AI policy">
        <label>
          <input
            type="checkbox"
            checked={readiness?.automation_enabled ?? false}
            disabled={!canManage || updatePolicy.isPending}
            onChange={(event) => updatePolicy.mutate({ automation_enabled: event.target.checked })}
          />
          <span>
            <strong>AI automation</strong>
            <small>Classification, routing, drafting, and agent execution</small>
          </span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={readiness?.can_send_customer_messages ?? false}
            disabled={!canManage || !readiness?.configured || updatePolicy.isPending}
            onChange={(event) =>
              updatePolicy.mutate({ can_send_customer_messages: event.target.checked })
            }
          />
          <span>
            <strong>Customer auto-send</strong>
            <small>Allow active agents to send under an audited policy</small>
          </span>
        </label>
      </div>

      <div className="people-console-toolbar ai-studio-toolbar">
        <div className="people-console-tabs" role="tablist" aria-label="AI Studio views">
          <button
            type="button"
            role="tab"
            aria-selected={view === 'agents'}
            className={view === 'agents' ? 'active' : ''}
            onClick={() => setView('agents')}
          >
            <Bot size={14} />
            Agents
            <span>{agentsQuery.data?.length ?? 0}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === 'decisions'}
            className={view === 'decisions' ? 'active' : ''}
            onClick={() => setView('decisions')}
          >
            <Activity size={14} />
            Decision log
          </button>
        </div>
        {view === 'agents' ? (
          <button type="button" className="primary-action" disabled={!canManage} onClick={openCreateForm}>
            <Plus size={14} />
            New AI agent
          </button>
        ) : null}
      </div>

      {notice ? <p className="campaign-notice" role="status">{notice}</p> : null}
      {mutationError ? (
        <p className="campaign-notice error" role="alert">{errorMessage(mutationError)}</p>
      ) : null}

      {view === 'agents' ? (
        <>
          {formOpen ? (
            <form className="ai-agent-form" onSubmit={submit}>
              <label>
                <span>Name</span>
                <input
                  value={draft.name}
                  onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                  maxLength={180}
                  required
                />
              </label>
              <label>
                <span>Description</span>
                <input
                  value={draft.description}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, description: event.target.value }))
                  }
                  maxLength={500}
                />
              </label>
              <label>
                <span>Languages</span>
                <input
                  value={draft.languages}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, languages: event.target.value }))
                  }
                  placeholder="en, fr"
                  required
                />
              </label>
              <label>
                <span>Handoff team</span>
                <input
                  value={draft.handoffTeam}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, handoffTeam: event.target.value }))
                  }
                  placeholder="General Support"
                />
              </label>
              <fieldset className="ai-agent-channels">
                <legend>Channels</legend>
                <div>
                  {aiChannels.map((channel) => (
                    <label key={channel}>
                      <input
                        type="checkbox"
                        checked={draft.channels.includes(channel)}
                        onChange={() => toggleChannel(channel)}
                      />
                      <span>{channel}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="ai-agent-confidence">
                <span>Confidence threshold: {draft.confidenceThreshold}%</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={draft.confidenceThreshold}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      confidenceThreshold: Number(event.target.value),
                    }))
                  }
                />
              </label>
              <label className="ai-agent-instructions">
                <span>Instructions</span>
                <textarea
                  value={draft.instructions}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, instructions: event.target.value }))
                  }
                  maxLength={12000}
                  rows={5}
                  required
                />
              </label>
              <label className="ai-agent-auto-send">
                <input
                  type="checkbox"
                  checked={draft.autoSend}
                  disabled={!readiness?.can_send_customer_messages}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, autoSend: event.target.checked }))
                  }
                />
                <span>Allow this agent to send customer messages automatically</span>
              </label>
              <div className="campaign-form-actions">
                <button type="button" onClick={closeForm}>Cancel</button>
                <button type="submit" className="primary-action" disabled={!canSubmit || busy}>
                  {busy ? <RefreshCw size={14} className="spin-icon" /> : <ShieldCheck size={14} />}
                  {editingId ? 'Save changes' : 'Save draft'}
                </button>
              </div>
            </form>
          ) : null}

          {agentsQuery.isPending ? (
            <p className="report-catalog-state">Loading AI agents...</p>
          ) : agentsQuery.data?.length ? (
            <div className="ai-agent-list">
              {agentsQuery.data.map((agent) => (
                <article key={agent.id}>
                  <span className="ai-agent-icon"><Bot size={18} /></span>
                  <div className="ai-agent-identity">
                    <strong>{agent.name}</strong>
                    <span>{agent.description || 'No description'}</span>
                    <small>{agent.channels.join(', ')} / {agent.languages.join(', ')}</small>
                  </div>
                  <div className="ai-agent-policy">
                    <strong>{agent.confidence_threshold}%</strong>
                    <span>Confidence</span>
                    <small>{agent.auto_send ? 'Auto-send allowed' : 'Human review'}</small>
                  </div>
                  <div className="ai-agent-actions">
                    <button type="button" onClick={() => openEditForm(agent)} disabled={!canManage}>
                      <Pencil size={13} />
                      Edit
                    </button>
                    <button
                      type="button"
                      disabled={!canManage || updateAgent.isPending}
                      onClick={() =>
                        updateAgent.mutate({
                          id: agent.id,
                          body: { status: agent.status === 'active' ? 'paused' : 'active' },
                        })
                      }
                    >
                      {agent.status === 'active' ? <Pause size={13} /> : <Play size={13} />}
                      {agent.status === 'active' ? 'Pause' : 'Activate'}
                    </button>
                  </div>
                  <em className={`chip status-${agent.status === 'active' ? 'done' : agent.status === 'draft' ? 'progress' : 'pending'}`}>
                    {agent.status}
                  </em>
                </article>
              ))}
            </div>
          ) : (
            <div className="campaign-empty">
              <Bot size={20} />
              <strong>No AI agents in this market</strong>
              <span>Create a draft with channels, instructions, confidence, and handoff policy.</span>
            </div>
          )}
        </>
      ) : decisionsQuery.isPending ? (
        <p className="report-catalog-state">Loading AI decisions...</p>
      ) : decisionsQuery.data?.length ? (
        <div className="ai-decision-list" aria-label="AI decision log">
          {decisionsQuery.data.map((decision) => (
            <article key={decision.id}>
              <span className="ai-decision-confidence">{decision.confidence}%</span>
              <span>
                <strong>{decision.ticket_number} / {decision.decision_type}</strong>
                <p>{decision.summary}</p>
                <small>{decision.model_version} / {formatTimestamp(decision.created_at)}</small>
              </span>
              <em className={`chip status-${decision.override_allowed ? 'progress' : 'done'}`}>
                {decision.override_allowed ? 'Reviewable' : 'Policy locked'}
              </em>
            </article>
          ))}
        </div>
      ) : (
        <div className="campaign-empty">
          <Activity size={20} />
          <strong>No AI decisions recorded</strong>
          <span>Audited decisions will appear after AI-assisted ticket work runs.</span>
        </div>
      )}
    </div>
  )
}
