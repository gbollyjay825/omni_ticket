import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Copy,
  ExternalLink,
  MessageSquare,
  Plus,
  RefreshCw,
  Settings,
  Users,
} from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'

import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'
import { getBackendBaseUrl, type BackendSession } from '../../backend'

type BusinessHours = components['schemas']['BusinessHours']
type Channel = components['schemas']['ChannelType']
type SupportGroup = components['schemas']['SupportGroup']
type WidgetSettings = components['schemas']['WidgetSettings']

const groupChannels: Channel[] = ['email', 'chat', 'whatsapp', 'facebook', 'instagram', 'sms']
const weekdaySchedule = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].map((day) => ({
  day,
  enabled: true,
  open: '09:00',
  close: '17:00',
}))

interface OmnichatSettingsConsoleProps {
  session: BackendSession | null
  canManage: boolean
  onOpenAdmin: () => void
}

interface WidgetDraft {
  enabled: boolean
  displayName: string
  welcomeMessage: string
  primaryColor: string
  launcherLabel: string
  position: string
  autoOpenSeconds: number
  collectEmail: boolean
  offlineMessage: string
}

const defaultWidgetDraft: WidgetDraft = {
  enabled: false,
  displayName: 'Chat with us',
  welcomeMessage: 'Hi! How can we help you today?',
  primaryColor: '#0b5eea',
  launcherLabel: 'Support',
  position: 'bottom-right',
  autoOpenSeconds: 0,
  collectEmail: true,
  offlineMessage: "We're offline right now. Leave a message and we'll reply by email.",
}

function widgetDraftFromSettings(widget: WidgetSettings): WidgetDraft {
  return {
    enabled: widget.enabled,
    displayName: widget.display_name,
    welcomeMessage: widget.welcome_message,
    primaryColor: widget.primary_color,
    launcherLabel: widget.launcher_label,
    position: widget.position,
    autoOpenSeconds: widget.auto_open_seconds,
    collectEmail: widget.collect_email,
    offlineMessage: widget.offline_message,
  }
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'detail' in error && typeof error.detail === 'string') {
    return error.detail
  }
  return 'Omnichat settings are unavailable.'
}

export function OmnichatSettingsConsole({
  session,
  canManage,
  onOpenAdmin,
}: OmnichatSettingsConsoleProps) {
  const client = useMemo(() => createOmniApiClient(session), [session])
  const queryClient = useQueryClient()
  const [view, setView] = useState<'widget' | 'groups' | 'hours'>('widget')
  const [notice, setNotice] = useState('')
  const [groupFormOpen, setGroupFormOpen] = useState(false)
  const [hoursFormOpen, setHoursFormOpen] = useState(false)
  const [widgetOverrides, setWidgetOverrides] = useState<Partial<WidgetDraft>>({})
  const [groupDraft, setGroupDraft] = useState({
    name: '',
    description: '',
    teamEmail: '',
    channels: ['chat'] as Channel[],
  })
  const [hoursDraft, setHoursDraft] = useState({
    name: '',
    timezone: session?.market.timezone ?? 'Africa/Lagos',
  })

  const widgetQuery = useQuery({
    queryKey: ['widget-settings', session?.market.id],
    enabled: Boolean(session) && canManage,
    queryFn: async (): Promise<WidgetSettings> => {
      const response = await client.GET('/api/v1/widget-settings')
      if (response.error) throw response.error
      if (!response.data) throw new Error('Widget settings did not return data.')
      return response.data
    },
  })

  const groupsQuery = useQuery({
    queryKey: ['support-groups', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<SupportGroup[]> => {
      const response = await client.GET('/api/v1/support-groups')
      if (response.error) throw response.error
      return response.data ?? []
    },
  })

  const hoursQuery = useQuery({
    queryKey: ['business-hours', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<BusinessHours[]> => {
      const response = await client.GET('/api/v1/business-hours')
      if (response.error) throw response.error
      return response.data ?? []
    },
  })

  const widgetDraft = {
    ...(widgetQuery.data ? widgetDraftFromSettings(widgetQuery.data) : defaultWidgetDraft),
    ...widgetOverrides,
  }
  const appOrigin = typeof window === 'undefined' ? 'https://omni.wakanow.com' : window.location.origin
  const apiOrigin = getBackendBaseUrl().replace(/\/api\/v1\/?$/, '')
  const apiAttribute = apiOrigin === appOrigin ? '' : ` data-api-url="${apiOrigin}"`
  const widgetEmbedCode = `<script src="${appOrigin}/omni-widget.js" data-market="${session?.market.code.toLowerCase() ?? 'ng'}"${apiAttribute}></script>`
  const widgetPreviewUrl = `${appOrigin}/widget-preview.html`

  const saveWidget = useMutation({
    mutationFn: async () => {
      const response = await client.PATCH('/api/v1/widget-settings', {
        body: {
          enabled: widgetDraft.enabled,
          display_name: widgetDraft.displayName.trim(),
          welcome_message: widgetDraft.welcomeMessage.trim(),
          primary_color: widgetDraft.primaryColor,
          launcher_label: widgetDraft.launcherLabel.trim(),
          position: widgetDraft.position,
          auto_open_seconds: widgetDraft.autoOpenSeconds,
          collect_email: widgetDraft.collectEmail,
          offline_message: widgetDraft.offlineMessage.trim(),
        },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['widget-settings', session?.market.id] })
      setWidgetOverrides({})
      setNotice('Messenger settings saved.')
    },
  })

  const createGroup = useMutation({
    mutationFn: async () => {
      const response = await client.POST('/api/v1/support-groups', {
        body: {
          name: groupDraft.name.trim(),
          description: groupDraft.description.trim(),
          team_email: groupDraft.teamEmail.trim() || null,
          active: true,
          channels: groupDraft.channels,
          skills: [],
        },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (group) => {
      await queryClient.invalidateQueries({ queryKey: ['support-groups', session?.market.id] })
      setGroupDraft({ name: '', description: '', teamEmail: '', channels: ['chat'] })
      setGroupFormOpen(false)
      setNotice(`${group?.name ?? 'Group'} created.`)
    },
  })

  const updateGroup = useMutation({
    mutationFn: async ({ id, active }: { id: string; active: boolean }) => {
      const response = await client.PATCH('/api/v1/support-groups/{group_id}', {
        params: { path: { group_id: id } },
        body: { active },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (group) => {
      await queryClient.invalidateQueries({ queryKey: ['support-groups', session?.market.id] })
      setNotice(`${group?.name ?? 'Group'} is ${group?.active ? 'active' : 'paused'}.`)
    },
  })

  const createHours = useMutation({
    mutationFn: async () => {
      const response = await client.POST('/api/v1/business-hours', {
        body: {
          name: hoursDraft.name.trim(),
          timezone: hoursDraft.timezone.trim(),
          active: true,
          days: weekdaySchedule,
        },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (schedule) => {
      await queryClient.invalidateQueries({ queryKey: ['business-hours', session?.market.id] })
      setHoursDraft({ name: '', timezone: session?.market.timezone ?? 'Africa/Lagos' })
      setHoursFormOpen(false)
      setNotice(`${schedule?.name ?? 'Business hours'} created.`)
    },
  })

  const updateHours = useMutation({
    mutationFn: async ({ id, active }: { id: string; active: boolean }) => {
      const response = await client.PATCH('/api/v1/business-hours/{business_hours_id}', {
        params: { path: { business_hours_id: id } },
        body: { active },
      })
      if (response.error) throw response.error
      return response.data
    },
    onSuccess: async (schedule) => {
      await queryClient.invalidateQueries({ queryKey: ['business-hours', session?.market.id] })
      setNotice(`${schedule?.name ?? 'Business hours'} is ${schedule?.active ? 'active' : 'paused'}.`)
    },
  })

  const queryError = widgetQuery.error ?? groupsQuery.error ?? hoursQuery.error
  const mutationError =
    saveWidget.error ?? createGroup.error ?? updateGroup.error ?? createHours.error ?? updateHours.error

  function submitGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (groupDraft.name.trim().length >= 2 && groupDraft.channels.length && !createGroup.isPending) {
      createGroup.mutate()
    }
  }

  function submitHours(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (hoursDraft.name.trim().length >= 2 && hoursDraft.timezone.trim() && !createHours.isPending) {
      createHours.mutate()
    }
  }

  function toggleGroupChannel(channel: Channel) {
    setGroupDraft((current) => ({
      ...current,
      channels: current.channels.includes(channel)
        ? current.channels.filter((item) => item !== channel)
        : [...current.channels, channel],
    }))
  }

  async function copyWidgetEmbedCode() {
    try {
      await navigator.clipboard.writeText(widgetEmbedCode)
      setNotice('Embed code copied.')
    } catch {
      setNotice('Clipboard access is unavailable. Select the embed code to copy it.')
    }
  }

  if (!canManage) {
    return (
      <div className="omnichat-settings-access">
        <Settings size={20} />
        <strong>Admin permission required</strong>
        <span>Widget, routing group, and business-hours changes are restricted to admins.</span>
      </div>
    )
  }

  if (queryError) {
    return (
      <div className="report-catalog-state error" role="alert">
        <AlertTriangle size={16} />
        <span>{errorMessage(queryError)}</span>
        <button
          type="button"
          onClick={() => {
            void widgetQuery.refetch()
            void groupsQuery.refetch()
            void hoursQuery.refetch()
          }}
        >
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="omnichat-settings-console">
      <div className="people-console-toolbar omnichat-settings-toolbar">
        <div className="people-console-tabs" role="tablist" aria-label="Omnichat settings views">
          <button type="button" role="tab" aria-selected={view === 'widget'} className={view === 'widget' ? 'active' : ''} onClick={() => setView('widget')}>
            <MessageSquare size={14} />
            Messenger
          </button>
          <button type="button" role="tab" aria-selected={view === 'groups'} className={view === 'groups' ? 'active' : ''} onClick={() => setView('groups')}>
            <Users size={14} />
            Groups
            <span>{groupsQuery.data?.length ?? 0}</span>
          </button>
          <button type="button" role="tab" aria-selected={view === 'hours'} className={view === 'hours' ? 'active' : ''} onClick={() => setView('hours')}>
            <Clock3 size={14} />
            Business hours
            <span>{hoursQuery.data?.length ?? 0}</span>
          </button>
        </div>
        <button type="button" className="secondary-action" onClick={onOpenAdmin}>
          <Settings size={14} />
          All settings
        </button>
      </div>

      {notice ? <p className="campaign-notice" role="status">{notice}</p> : null}
      {mutationError ? <p className="campaign-notice error" role="alert">{errorMessage(mutationError)}</p> : null}

      {view === 'widget' ? (
        widgetQuery.isPending ? (
          <p className="report-catalog-state">Loading messenger settings...</p>
        ) : (
          <form className="widget-settings-form" onSubmit={(event) => { event.preventDefault(); saveWidget.mutate() }}>
            <div className="widget-settings-status">
              <span className={widgetDraft.enabled ? 'active' : ''}>
                {widgetDraft.enabled ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                {widgetDraft.enabled ? 'Messenger enabled' : 'Messenger disabled'}
              </span>
              <label>
                <input type="checkbox" checked={widgetDraft.enabled} onChange={(event) => setWidgetOverrides((current) => ({ ...current, enabled: event.target.checked }))} />
                <span>Enabled</span>
              </label>
            </div>
            <label>
              <span>Display name</span>
              <input value={widgetDraft.displayName} onChange={(event) => setWidgetOverrides((current) => ({ ...current, displayName: event.target.value }))} maxLength={120} required />
            </label>
            <label>
              <span>Launcher label</span>
              <input value={widgetDraft.launcherLabel} onChange={(event) => setWidgetOverrides((current) => ({ ...current, launcherLabel: event.target.value }))} maxLength={80} required />
            </label>
            <label>
              <span>Position</span>
              <select value={widgetDraft.position} onChange={(event) => setWidgetOverrides((current) => ({ ...current, position: event.target.value }))}>
                <option value="bottom-right">Bottom right</option>
                <option value="bottom-left">Bottom left</option>
              </select>
            </label>
            <label>
              <span>Brand color</span>
              <span className="widget-color-control">
                <input type="color" value={widgetDraft.primaryColor} onChange={(event) => setWidgetOverrides((current) => ({ ...current, primaryColor: event.target.value }))} />
                <input value={widgetDraft.primaryColor} onChange={(event) => setWidgetOverrides((current) => ({ ...current, primaryColor: event.target.value }))} maxLength={20} />
              </span>
            </label>
            <label>
              <span>Auto-open seconds</span>
              <input type="number" min="0" max="600" value={widgetDraft.autoOpenSeconds} onChange={(event) => setWidgetOverrides((current) => ({ ...current, autoOpenSeconds: Number(event.target.value) }))} />
            </label>
            <label className="widget-settings-full">
              <span>Welcome message</span>
              <textarea value={widgetDraft.welcomeMessage} onChange={(event) => setWidgetOverrides((current) => ({ ...current, welcomeMessage: event.target.value }))} maxLength={500} rows={3} />
            </label>
            <label className="widget-settings-full">
              <span>Offline message</span>
              <textarea value={widgetDraft.offlineMessage} onChange={(event) => setWidgetOverrides((current) => ({ ...current, offlineMessage: event.target.value }))} maxLength={500} rows={3} />
            </label>
            <label className="widget-collect-email">
              <input type="checkbox" checked={widgetDraft.collectEmail} onChange={(event) => setWidgetOverrides((current) => ({ ...current, collectEmail: event.target.checked }))} />
              <span>Collect customer email before chat</span>
            </label>
            <div className="widget-install-panel">
              <div className="widget-install-heading">
                <span>
                  <strong>Installation</strong>
                  <small>{session?.market.code.toUpperCase() ?? 'NG'} market</small>
                </span>
                <a className="secondary-action" href={widgetPreviewUrl} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} />
                  Preview
                </a>
              </div>
              <label>
                <span>Embed code</span>
                <textarea value={widgetEmbedCode} rows={3} readOnly spellCheck={false} />
              </label>
              <button type="button" className="secondary-action" onClick={() => void copyWidgetEmbedCode()}>
                <Copy size={14} />
                Copy code
              </button>
            </div>
            <div className="campaign-form-actions">
              <button type="submit" className="primary-action" disabled={saveWidget.isPending}>
                {saveWidget.isPending ? <RefreshCw size={14} className="spin-icon" /> : <CheckCircle2 size={14} />}
                Save messenger
              </button>
            </div>
          </form>
        )
      ) : null}

      {view === 'groups' ? (
        <>
          <div className="settings-list-toolbar">
            <strong>{groupsQuery.data?.length ?? 0} routing groups</strong>
            <button type="button" className="primary-action" onClick={() => setGroupFormOpen((open) => !open)}><Plus size={14} />New group</button>
          </div>
          {groupFormOpen ? (
            <form className="settings-create-form" onSubmit={submitGroup}>
              <label><span>Name</span><input value={groupDraft.name} onChange={(event) => setGroupDraft((current) => ({ ...current, name: event.target.value }))} required /></label>
              <label><span>Team email</span><input type="email" value={groupDraft.teamEmail} onChange={(event) => setGroupDraft((current) => ({ ...current, teamEmail: event.target.value }))} /></label>
              <label className="settings-form-full"><span>Description</span><textarea value={groupDraft.description} onChange={(event) => setGroupDraft((current) => ({ ...current, description: event.target.value }))} rows={2} /></label>
              <fieldset className="settings-form-full"><legend>Channels</legend><div>{groupChannels.map((channel) => <label key={channel}><input type="checkbox" checked={groupDraft.channels.includes(channel)} onChange={() => toggleGroupChannel(channel)} /><span>{channel}</span></label>)}</div></fieldset>
              <div className="campaign-form-actions settings-form-full"><button type="button" onClick={() => setGroupFormOpen(false)}>Cancel</button><button type="submit" className="primary-action" disabled={createGroup.isPending || groupDraft.name.trim().length < 2 || !groupDraft.channels.length}><Plus size={14} />Create group</button></div>
            </form>
          ) : null}
          <div className="settings-record-list">
            {groupsQuery.data?.map((group) => (
              <article key={group.id}>
                <span className="settings-record-icon"><Users size={15} /></span>
                <span><strong>{group.name}</strong><small>{group.channels?.join(', ') || 'No channels'} / {group.team_email || 'No team email'}</small></span>
                <span><strong>{group.member_count}</strong><small>members</small></span>
                <span><strong>{group.open_ticket_count}</strong><small>open / {group.sla_risk_count} at risk</small></span>
                <button type="button" onClick={() => updateGroup.mutate({ id: group.id, active: !group.active })}>{group.active ? 'Pause' : 'Activate'}</button>
                <em className={`chip status-${group.active ? 'done' : 'pending'}`}>{group.active ? 'Active' : 'Paused'}</em>
              </article>
            ))}
          </div>
        </>
      ) : null}

      {view === 'hours' ? (
        <>
          <div className="settings-list-toolbar">
            <strong>{hoursQuery.data?.length ?? 0} schedules</strong>
            <button type="button" className="primary-action" onClick={() => setHoursFormOpen((open) => !open)}><Plus size={14} />New schedule</button>
          </div>
          {hoursFormOpen ? (
            <form className="settings-create-form" onSubmit={submitHours}>
              <label><span>Name</span><input value={hoursDraft.name} onChange={(event) => setHoursDraft((current) => ({ ...current, name: event.target.value }))} required /></label>
              <label><span>Timezone</span><input value={hoursDraft.timezone} onChange={(event) => setHoursDraft((current) => ({ ...current, timezone: event.target.value }))} required /></label>
              <p className="settings-form-full">Monday-Friday / 09:00-17:00</p>
              <div className="campaign-form-actions settings-form-full"><button type="button" onClick={() => setHoursFormOpen(false)}>Cancel</button><button type="submit" className="primary-action" disabled={createHours.isPending || hoursDraft.name.trim().length < 2}><Plus size={14} />Create schedule</button></div>
            </form>
          ) : null}
          <div className="settings-record-list business-hours-records">
            {hoursQuery.data?.map((schedule) => (
              <article key={schedule.id}>
                <span className="settings-record-icon"><Clock3 size={15} /></span>
                <span><strong>{schedule.name}</strong><small>{schedule.timezone}</small></span>
                <span><strong>{(schedule.days ?? []).filter((day) => day.enabled).length}</strong><small>active days</small></span>
                <span><strong>{(schedule.days ?? []).find((day) => day.enabled)?.open ?? '--'}</strong><small>first opening</small></span>
                <button type="button" onClick={() => updateHours.mutate({ id: schedule.id, active: !schedule.active })}>{schedule.active ? 'Pause' : 'Activate'}</button>
                <em className={`chip status-${schedule.active ? 'done' : 'pending'}`}>{schedule.active ? 'Active' : 'Paused'}</em>
              </article>
            ))}
          </div>
        </>
      ) : null}
    </div>
  )
}
