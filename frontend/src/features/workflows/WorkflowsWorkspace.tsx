import { useMemo, useState } from 'react'
import {
  ChevronDown,
  Clock3,
  FileText,
  GripVertical,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  TicketCheck,
  X,
} from 'lucide-react'
import type {
  BackendCreateAutomationRuleInput,
  BackendUpdateRuleInput,
} from '../../backend'
import type { AutomationRule, SlaPolicy } from '../../domain'
import './workflows-workspace.css'

type RuleStage = 'ticket_creation' | 'ticket_updates' | 'time_triggers'
type WorkspaceView = 'automations' | 'sla'

interface RuleDraft {
  name: string
  trigger: string
  action: string
  enabled: boolean
}

interface WorkflowsWorkspaceProps {
  rules: AutomationRule[]
  slaPolicies: SlaPolicy[]
  onToggleRule: (ruleId: string) => Promise<void> | void
  onCreateRule: (input: BackendCreateAutomationRuleInput) => Promise<void>
  onUpdateRule: (ruleId: string, input: BackendUpdateRuleInput) => Promise<void>
}

const STAGES: Array<{ id: RuleStage; label: string; description: string }> = [
  {
    id: 'ticket_creation',
    label: 'Ticket creation',
    description: 'These rules automate next steps as soon as a customer writes to you. Set priority, route work, and apply the right response path. Rules run sequentially.',
  },
  {
    id: 'ticket_updates',
    label: 'Ticket updates',
    description: 'These rules run when an agent or customer changes a ticket, replies, updates ownership, or moves its status.',
  },
  {
    id: 'time_triggers',
    label: 'Hourly triggers',
    description: 'These rules scan tickets each hour for due times, inactivity, SLA risk, and scheduled follow-up conditions.',
  },
]

const emptyDraft: RuleDraft = { name: '', trigger: '', action: '', enabled: true }

function ruleStage(rule: AutomationRule): RuleStage {
  const trigger = rule.trigger.toLowerCase()
  if (trigger.includes('[time_triggers]') || /(hour|schedule|due|sla|inactive|time)/.test(trigger)) return 'time_triggers'
  if (trigger.includes('[ticket_updates]') || /(update|reply|status|assign|resolve|close|reopen)/.test(trigger)) return 'ticket_updates'
  return 'ticket_creation'
}

function cleanTrigger(trigger: string) {
  return trigger.replace(/^\[(ticket_creation|ticket_updates|time_triggers)\]\s*/i, '')
}

function stageTrigger(stage: RuleStage, trigger: string) {
  return `[${stage}] ${cleanTrigger(trigger).trim()}`
}

function dateLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Never'
  return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(date)
}

export function WorkflowsWorkspace({
  rules,
  slaPolicies,
  onToggleRule,
  onCreateRule,
  onUpdateRule,
}: WorkflowsWorkspaceProps) {
  const [view, setView] = useState<WorkspaceView>('automations')
  const [stage, setStage] = useState<RuleStage>('ticket_creation')
  const [search, setSearch] = useState('')
  const [dialog, setDialog] = useState<'create' | 'edit' | null>(null)
  const [editingId, setEditingId] = useState('')
  const [draft, setDraft] = useState<RuleDraft>(emptyDraft)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const selectedStage = STAGES.find((item) => item.id === stage) ?? STAGES[0]
  const visibleRules = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return rules.filter((rule) => {
      if (ruleStage(rule) !== stage) return false
      if (!needle) return true
      return `${rule.name} ${rule.trigger} ${rule.action}`.toLowerCase().includes(needle)
    })
  }, [rules, search, stage])

  function openCreate() {
    setEditingId('')
    setDraft(emptyDraft)
    setError('')
    setDialog('create')
  }

  function openEdit(rule: AutomationRule) {
    setEditingId(rule.id)
    setDraft({
      name: rule.name,
      trigger: cleanTrigger(rule.trigger),
      action: rule.action,
      enabled: rule.status === 'active',
    })
    setError('')
    setDialog('edit')
  }

  async function saveRule() {
    setBusy(true)
    setError('')
    try {
      const input = {
        name: draft.name.trim(),
        trigger: stageTrigger(stage, draft.trigger),
        action: draft.action.trim(),
        enabled: draft.enabled,
      }
      if (dialog === 'edit') await onUpdateRule(editingId, input)
      else await onCreateRule(input)
      setDialog(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The automation rule could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="workflows-workspace" aria-label="Workflows workspace">
      <header className="workflows-titlebar">
        <div>
          <span>Admin</span>
          <h2>Automations</h2>
        </div>
        <div className="workflows-view-switch" role="tablist" aria-label="Workflow settings">
          <button type="button" role="tab" aria-selected={view === 'automations'} onClick={() => setView('automations')}>Automations</button>
          <button type="button" role="tab" aria-selected={view === 'sla'} onClick={() => setView('sla')}>SLA policies</button>
        </div>
      </header>

      {view === 'automations' ? (
        <>
          <div className="workflow-stage-heading">
            <strong>Rules that run on:</strong>
            <nav aria-label="Automation stages">
              {STAGES.map((item) => (
                <button key={item.id} type="button" className={stage === item.id ? 'active' : ''} onClick={() => setStage(item.id)}>{item.label}</button>
              ))}
            </nav>
            <label className="workflow-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search rules" aria-label="Search automation rules" /></label>
          </div>

          <p className="workflow-description">{selectedStage.description}</p>

          <div className="workflow-commandbar">
            <button className="icon-button" type="button" aria-label="Reorder rules" title="Reorder rules"><GripVertical size={17} /></button>
            <button type="button" className="execution-mode">Executing all matching rules <ChevronDown size={15} /></button>
            <span />
            <button type="button"><FileText size={16} /> Templates</button>
            <button type="button" className="primary-action" onClick={openCreate}><Plus size={16} /> New rule</button>
          </div>

          <div className="workflow-rule-list" aria-live="polite">
            {visibleRules.length === 0 ? (
              <div className="workflow-empty"><TicketCheck size={28} /><strong>No matching rules</strong><span>Create a rule for {selectedStage.label.toLowerCase()} or change the search.</span></div>
            ) : visibleRules.map((rule, index) => (
              <article className="workflow-rule-card" key={rule.id}>
                <div className="workflow-rule-main">
                  <b>{index + 1}.</b>
                  <div>
                    <button type="button" className="rule-name" onClick={() => openEdit(rule)}>{rule.name}</button>
                    <p>If {cleanTrigger(rule.trigger)} <strong>{rule.action}</strong></p>
                  </div>
                  <button type="button" className="rule-toggle" aria-label={`${rule.status === 'active' ? 'Pause' : 'Activate'} ${rule.name}`} aria-pressed={rule.status === 'active'} onClick={() => void onToggleRule(rule.id)}><span /></button>
                  <button type="button" className="icon-button" aria-label={`Edit ${rule.name}`} onClick={() => openEdit(rule)}><Pencil size={15} /></button>
                  <button type="button" className="icon-button" aria-label={`More actions for ${rule.name}`}><MoreHorizontal size={17} /></button>
                </div>
                <footer>
                  <span>Last run: <strong>{dateLabel(rule.lastFired)}</strong></span>
                  <span>By: <strong>{rule.owner}</strong></span>
                  <span>Failures: <strong>{rule.failures}</strong></span>
                </footer>
              </article>
            ))}
          </div>
        </>
      ) : (
        <div className="sla-parity-view">
          <div className="sla-parity-intro"><Clock3 size={20} /><div><h3>SLA policies</h3><p>Set first-response and resolution expectations by priority and operating calendar.</p></div></div>
          <div className="sla-parity-list">
            {slaPolicies.map((policy, index) => (
              <article key={policy.id}>
                <b>{index + 1}.</b>
                <div><strong>{policy.name}</strong><span>{policy.businessHours}</span></div>
                <div><span>Priority</span><strong>{policy.priority}</strong></div>
                <div><span>First response</span><strong>{policy.firstResponseMinutes} min</strong></div>
                <div><span>Resolution</span><strong>{policy.resolutionMinutes} min</strong></div>
              </article>
            ))}
          </div>
        </div>
      )}

      {dialog ? (
        <div className="workflow-modal-backdrop" role="presentation" onMouseDown={() => setDialog(null)}>
          <form className="workflow-rule-dialog" aria-label={dialog === 'create' ? 'New automation rule' : 'Edit automation rule'} onSubmit={(event) => { event.preventDefault(); void saveRule() }} onMouseDown={(event) => event.stopPropagation()}>
            <header><div><span>{selectedStage.label}</span><h3>{dialog === 'create' ? 'New rule' : 'Edit rule'}</h3></div><button type="button" className="icon-button" aria-label="Close automation rule" onClick={() => setDialog(null)}><X size={17} /></button></header>
            <div className="workflow-rule-form">
              <label><span>Rule name</span><input required value={draft.name} onChange={(event) => setDraft((value) => ({ ...value, name: event.target.value }))} /></label>
              <label><span>When these conditions match</span><textarea required rows={4} value={draft.trigger} onChange={(event) => setDraft((value) => ({ ...value, trigger: event.target.value }))} placeholder="Source is email and priority is urgent" /></label>
              <label><span>Perform these actions</span><textarea required rows={4} value={draft.action} onChange={(event) => setDraft((value) => ({ ...value, action: event.target.value }))} placeholder="Assign to Customer Resolution and notify supervisor" /></label>
              <label className="workflow-enabled"><input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft((value) => ({ ...value, enabled: event.target.checked }))} /><span>Activate this rule</span></label>
              {error ? <p className="workflow-form-error" role="alert">{error}</p> : null}
            </div>
            <footer><button type="button" onClick={() => setDialog(null)}>Cancel</button><button type="submit" className="primary-action" disabled={busy || !draft.name.trim() || !draft.trigger.trim() || !draft.action.trim()}>{busy ? 'Saving…' : dialog === 'create' ? 'Create rule' : 'Save changes'}</button></footer>
          </form>
        </div>
      ) : null}
    </section>
  )
}
