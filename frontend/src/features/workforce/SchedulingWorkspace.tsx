import { useMemo, useState } from 'react'
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  MapPin,
  MoreHorizontal,
  Plus,
  Search,
  UserRound,
  X,
} from 'lucide-react'
import type { AgentProfile, CustomerProfile, ServiceAppointment } from '../../domain'
import './scheduling-workspace.css'

const DAY_START_HOUR = 8
const DAY_END_HOUR = 18
const DAY_MINUTES = (DAY_END_HOUR - DAY_START_HOUR) * 60
const DURATIONS = [30, 45, 60, 90, 120, 180, 240]
const STATUSES = ['scheduled', 'en_route', 'in_progress', 'completed', 'cancelled']

export interface SchedulingCreateInput {
  title: string
  customerId: string
  technicianId: string
  scheduledAt: string
  durationMinutes: number
  location: string
  notes: string
}

export interface SchedulingUpdateInput {
  title?: string
  customerId?: string
  technicianId?: string
  scheduledAt?: string
  durationMinutes?: number
  status?: string
  location?: string
  notes?: string
}

interface SchedulingWorkspaceProps {
  appointments: ServiceAppointment[]
  technicians: AgentProfile[]
  customers: CustomerProfile[]
  onCreate: (input: SchedulingCreateInput) => Promise<boolean>
  onUpdate: (appointmentId: string, input: SchedulingUpdateInput) => Promise<boolean>
}

interface AppointmentDraft {
  title: string
  customerId: string
  technicianId: string
  scheduledAt: string
  durationMinutes: number
  status: string
  location: string
  notes: string
}

function localDateKey(value: string | Date) {
  const date = typeof value === 'string' ? new Date(value) : value
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function localDateTimeValue(value: string | Date) {
  const date = typeof value === 'string' ? new Date(value) : value
  return `${localDateKey(date)}T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function addDays(dateKey: string, days: number) {
  const date = new Date(`${dateKey}T12:00:00`)
  date.setDate(date.getDate() + days)
  return localDateKey(date)
}

function displayDate(dateKey: string) {
  return new Intl.DateTimeFormat('en-GB', {
    weekday: 'long',
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  }).format(new Date(`${dateKey}T12:00:00`))
}

function displayTime(value: string) {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).format(new Date(value))
}

function titleCase(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

function draftForAppointment(appointment: ServiceAppointment): AppointmentDraft {
  return {
    title: appointment.title,
    customerId: appointment.customerId,
    technicianId: appointment.technicianId,
    scheduledAt: localDateTimeValue(appointment.scheduledAt),
    durationMinutes: appointment.durationMinutes,
    status: appointment.status,
    location: appointment.location,
    notes: appointment.notes,
  }
}

function newDraft(dateKey: string, durationMinutes: number): AppointmentDraft {
  return {
    title: '',
    customerId: '',
    technicianId: '',
    scheduledAt: `${dateKey}T09:00`,
    durationMinutes,
    status: 'scheduled',
    location: '',
    notes: '',
  }
}

export function SchedulingWorkspace({
  appointments,
  technicians,
  customers,
  onCreate,
  onUpdate,
}: SchedulingWorkspaceProps) {
  const firstDate = appointments.length ? localDateKey(appointments[0].scheduledAt) : localDateKey(new Date())
  const [selectedDate, setSelectedDate] = useState(firstDate)
  const [taskFilter, setTaskFilter] = useState('unsolved')
  const [search, setSearch] = useState('')
  const [selectedAppointmentId, setSelectedAppointmentId] = useState(appointments[0]?.id ?? '')
  const [defaultDuration, setDefaultDuration] = useState(60)
  const [dialogMode, setDialogMode] = useState<'create' | 'edit' | null>(null)
  const [draft, setDraft] = useState<AppointmentDraft>(() => newDraft(firstDate, 60))
  const [busy, setBusy] = useState(false)

  const customerById = useMemo(
    () => new Map(customers.map((customer) => [customer.id, customer])),
    [customers],
  )
  const technicianById = useMemo(
    () => new Map(technicians.map((technician) => [technician.id, technician])),
    [technicians],
  )
  const sortedAppointments = useMemo(
    () => [...appointments].sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt)),
    [appointments],
  )
  const visibleTasks = sortedAppointments.filter((appointment) => {
    if (taskFilter === 'unsolved' && ['completed', 'cancelled'].includes(appointment.status)) return false
    if (taskFilter === 'completed' && appointment.status !== 'completed') return false
    if (taskFilter === 'unassigned' && appointment.technicianId) return false
    const customer = customerById.get(appointment.customerId)
    return `${appointment.title} ${customer?.name ?? ''} ${appointment.location}`
      .toLowerCase()
      .includes(search.trim().toLowerCase())
  })
  const dayAppointments = sortedAppointments.filter(
    (appointment) => localDateKey(appointment.scheduledAt) === selectedDate,
  )
  const timelineTechnicians = technicians
  const hasUnassigned = dayAppointments.some((appointment) => !appointment.technicianId)
  const timelineRows = hasUnassigned
    ? [{ id: '', name: 'Unassigned', role: 'Needs dispatch', avatar: '', availability: 'offline', skills: [], load: 0, capacity: 0, occupancy: 0, csat: 0, shift: '' } satisfies AgentProfile, ...timelineTechnicians]
    : timelineTechnicians
  const hourLabels = Array.from(
    { length: DAY_END_HOUR - DAY_START_HOUR + 1 },
    (_, index) => DAY_START_HOUR + index,
  )

  function selectAppointment(appointment: ServiceAppointment) {
    setSelectedAppointmentId(appointment.id)
    setSelectedDate(localDateKey(appointment.scheduledAt))
  }

  function openCreate() {
    setDraft(newDraft(selectedDate, defaultDuration))
    setDialogMode('create')
  }

  function openEdit(appointment: ServiceAppointment) {
    selectAppointment(appointment)
    setDraft(draftForAppointment(appointment))
    setDialogMode('edit')
  }

  async function saveDraft() {
    if (busy || !draft.title.trim() || !draft.scheduledAt) return
    setBusy(true)
    try {
      const payload = {
        title: draft.title.trim(),
        customerId: draft.customerId,
        technicianId: draft.technicianId,
        scheduledAt: new Date(draft.scheduledAt).toISOString(),
        durationMinutes: draft.durationMinutes,
        status: draft.status,
        location: draft.location.trim(),
        notes: draft.notes.trim(),
      }
      const saved = dialogMode === 'create'
        ? await onCreate(payload)
        : await onUpdate(selectedAppointmentId, payload)
      if (saved) setDialogMode(null)
    } finally {
      setBusy(false)
    }
  }

  async function dropAppointment(
    appointmentId: string,
    technicianId: string,
    minuteOffset: number,
  ) {
    const hour = DAY_START_HOUR + Math.floor(minuteOffset / 60)
    const minute = minuteOffset % 60
    const scheduledAt = new Date(
      `${selectedDate}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`,
    ).toISOString()
    setBusy(true)
    try {
      await onUpdate(appointmentId, { technicianId, scheduledAt })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="scheduling-workspace" aria-label="Scheduling workspace">
      <div className="scheduling-toolbar">
        <div className="scheduling-date-controls">
          <button type="button" className="icon-button" aria-label="Previous day" onClick={() => setSelectedDate((value) => addDays(value, -1))}>
            <ChevronLeft size={16} />
          </button>
          <button type="button" onClick={() => setSelectedDate(localDateKey(new Date()))}>Today</button>
          <button type="button" className="icon-button" aria-label="Next day" onClick={() => setSelectedDate((value) => addDays(value, 1))}>
            <ChevronRight size={16} />
          </button>
        </div>
        <strong><CalendarDays size={16} /> {displayDate(selectedDate)}</strong>
        <label>
          <span>Default duration</span>
          <select value={defaultDuration} onChange={(event) => setDefaultDuration(Number(event.target.value))}>
            {DURATIONS.map((minutes) => <option key={minutes} value={minutes}>{minutes} minutes</option>)}
          </select>
        </label>
        <button type="button" className="primary-action" onClick={openCreate}><Plus size={15} /> New service task</button>
      </div>

      <div className="scheduling-board">
        <aside className="service-task-pane" aria-label="Service tasks">
          <header><strong>Service tasks</strong><span>{visibleTasks.length}</span></header>
          <div className="service-task-filters">
            <select aria-label="Service task view" value={taskFilter} onChange={(event) => setTaskFilter(event.target.value)}>
              <option value="unsolved">Unsolved service tasks</option>
              <option value="all">All service tasks</option>
              <option value="unassigned">Unassigned service tasks</option>
              <option value="completed">Completed service tasks</option>
            </select>
            <label><Search size={15} /><input aria-label="Search service tasks" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search" /></label>
          </div>
          <div className="service-task-list">
            {visibleTasks.map((appointment) => {
              const customer = customerById.get(appointment.customerId)
              const technician = technicianById.get(appointment.technicianId)
              return (
                <article
                  key={appointment.id}
                  className={appointment.id === selectedAppointmentId ? 'selected' : ''}
                  draggable={!busy}
                  onDragStart={(event) => event.dataTransfer.setData('text/appointment-id', appointment.id)}
                  onClick={() => selectAppointment(appointment)}
                >
                  <div className="service-task-card-head">
                    <span className="service-task-avatar">{initials(customer?.name ?? appointment.title)}</span>
                    <span><strong>{customer?.name ?? 'Service customer'}</strong><small>{appointment.status === 'scheduled' ? 'Open' : titleCase(appointment.status)}</small></span>
                    <button type="button" aria-label={`Edit ${appointment.title}`} onClick={(event) => { event.stopPropagation(); openEdit(appointment) }}><MoreHorizontal size={16} /></button>
                  </div>
                  <h3>{appointment.title} <small>#{appointment.id.slice(-6)}</small></h3>
                  <p><MapPin size={13} /> {appointment.location || 'No service address'}</p>
                  <p><UserRound size={13} /> {technician?.name ?? 'Unassigned'}</p>
                  <footer><Clock3 size={13} /> {displayTime(appointment.scheduledAt)} · {appointment.durationMinutes} min</footer>
                </article>
              )
            })}
            {visibleTasks.length === 0 ? <div className="service-task-empty"><Search size={24} /><strong>No service tasks found</strong></div> : null}
          </div>
        </aside>

        <div className="technician-schedule" aria-label="Field technician schedule">
          <div className="schedule-scroll">
            <div className="schedule-time-header">
              <strong>Field Technicians</strong>
              <div className="schedule-hour-labels">
                {hourLabels.map((hour) => <span key={hour}>{String(hour).padStart(2, '0')}:00</span>)}
              </div>
            </div>
            {timelineRows.map((technician) => {
              const rowAppointments = dayAppointments.filter(
                (appointment) => appointment.technicianId === technician.id,
              )
              return (
                <div className="technician-row" key={technician.id || 'unassigned'}>
                  <div className="technician-label">
                    <span>{technician.id ? initials(technician.name) : '?'}</span>
                    <div><strong>{technician.name}</strong><small>{technician.role}</small></div>
                  </div>
                  <div
                    className="technician-time-grid"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault()
                      const appointmentId = event.dataTransfer.getData('text/appointment-id')
                      if (!appointmentId) return
                      const rect = event.currentTarget.getBoundingClientRect()
                      const rawMinutes = ((event.clientX - rect.left) / rect.width) * DAY_MINUTES
                      const minuteOffset = Math.max(0, Math.min(DAY_MINUTES - 15, Math.round(rawMinutes / 15) * 15))
                      void dropAppointment(appointmentId, technician.id, minuteOffset)
                    }}
                  >
                    {rowAppointments.map((appointment, index) => {
                      const date = new Date(appointment.scheduledAt)
                      const minuteOffset = (date.getHours() - DAY_START_HOUR) * 60 + date.getMinutes()
                      const left = Math.max(0, Math.min(98, (minuteOffset / DAY_MINUTES) * 100))
                      const width = Math.max(5, Math.min(100 - left, (appointment.durationMinutes / DAY_MINUTES) * 100))
                      return (
                        <button
                          key={appointment.id}
                          type="button"
                          draggable={!busy}
                          className={`schedule-block schedule-block-${index % 4} ${appointment.id === selectedAppointmentId ? 'selected' : ''}`}
                          style={{ left: `${left}%`, width: `${width}%` }}
                          onDragStart={(event) => event.dataTransfer.setData('text/appointment-id', appointment.id)}
                          onClick={() => openEdit(appointment)}
                          title={`${appointment.title}, ${displayTime(appointment.scheduledAt)}, ${appointment.durationMinutes} minutes`}
                        >
                          <small>{displayTime(appointment.scheduledAt)} · {appointment.durationMinutes}m</small>
                          <strong>{appointment.title}</strong>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )
            })}
            {timelineRows.length === 0 ? <div className="schedule-no-technicians"><UserRound size={28} /><strong>No active technicians</strong><span>Add agents in Admin before dispatching service work.</span></div> : null}
          </div>
        </div>
      </div>

      {dialogMode ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setDialogMode(null)}>
          <form className="modal-card service-task-dialog" aria-label={dialogMode === 'create' ? 'New service task' : 'Edit service task'} onSubmit={(event) => { event.preventDefault(); void saveDraft() }} onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-head"><div><span>Field service</span><h2>{dialogMode === 'create' ? 'New service task' : 'Edit service task'}</h2></div><button type="button" className="icon-button" aria-label="Close service task" onClick={() => setDialogMode(null)}><X size={16} /></button></div>
            <div className="service-task-form">
              <label className="service-task-form-wide"><span>Task title</span><input required value={draft.title} onChange={(event) => setDraft((value) => ({ ...value, title: event.target.value }))} /></label>
              <label><span>Customer</span><select value={draft.customerId} onChange={(event) => setDraft((value) => ({ ...value, customerId: event.target.value }))}><option value="">No customer</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label>
              <label><span>Technician</span><select value={draft.technicianId} onChange={(event) => setDraft((value) => ({ ...value, technicianId: event.target.value }))}><option value="">Unassigned</option>{timelineTechnicians.map((technician) => <option key={technician.id} value={technician.id}>{technician.name}</option>)}</select></label>
              <label><span>Scheduled at</span><input required type="datetime-local" value={draft.scheduledAt} onChange={(event) => setDraft((value) => ({ ...value, scheduledAt: event.target.value }))} /></label>
              <label><span>Duration</span><select value={draft.durationMinutes} onChange={(event) => setDraft((value) => ({ ...value, durationMinutes: Number(event.target.value) }))}>{DURATIONS.map((minutes) => <option key={minutes} value={minutes}>{minutes} minutes</option>)}</select></label>
              {dialogMode === 'edit' ? <label><span>Status</span><select value={draft.status} onChange={(event) => setDraft((value) => ({ ...value, status: event.target.value }))}>{STATUSES.map((status) => <option key={status} value={status}>{titleCase(status)}</option>)}</select></label> : null}
              <label className={dialogMode === 'edit' ? '' : 'service-task-form-wide'}><span>Location</span><input value={draft.location} onChange={(event) => setDraft((value) => ({ ...value, location: event.target.value }))} /></label>
              <label className="service-task-form-wide"><span>Notes</span><textarea rows={3} value={draft.notes} onChange={(event) => setDraft((value) => ({ ...value, notes: event.target.value }))} /></label>
            </div>
            <div className="modal-actions"><button type="button" onClick={() => setDialogMode(null)}>Cancel</button><button type="submit" className="primary-action" disabled={busy || !draft.title.trim() || !draft.scheduledAt}>{busy ? 'Saving…' : dialogMode === 'create' ? 'Create service task' : 'Save changes'}</button></div>
          </form>
        </div>
      ) : null}
    </section>
  )
}
