import { useState, type FormEvent } from 'react'
import {
  CheckSquare,
  ChevronDown,
  CircleDot,
  DatabaseZap,
  GripVertical,
  Hash,
  ListFilter,
  Plus,
  Search,
  TextCursorInput,
  Trash2,
  X,
} from 'lucide-react'

import type { CustomObject, CustomObjectField, TicketFieldType } from '../../domain'
import './custom-objects-workspace.css'

interface CustomObjectInput {
  key: string
  name: string
  description: string
  fields: CustomObjectField[]
  active?: boolean
}

interface CustomObjectsWorkspaceProps {
  objects: CustomObject[]
  canManage: boolean
  onCreate: (input: CustomObjectInput) => Promise<boolean>
  onUpdate: (objectId: string, input: Partial<Omit<CustomObjectInput, 'key'>>) => Promise<boolean>
}

const fieldTypes: { type: TicketFieldType; label: string; icon: typeof TextCursorInput }[] = [
  { type: 'text', label: 'Text', icon: TextCursorInput },
  { type: 'textarea', label: 'Paragraph', icon: TextCursorInput },
  { type: 'number', label: 'Number', icon: Hash },
  { type: 'date', label: 'Date', icon: CircleDot },
  { type: 'select', label: 'Dropdown', icon: ChevronDown },
  { type: 'checkbox', label: 'Checkbox', icon: CheckSquare },
  { type: 'multiselect', label: 'Multi select', icon: ListFilter },
]

function fieldKey(type: TicketFieldType, fields: CustomObjectField[]) {
  const base = type === 'textarea' ? 'paragraph' : type
  let candidate = base
  let suffix = 2
  while (fields.some((field) => field.key === candidate)) {
    candidate = `${base}_${suffix}`
    suffix += 1
  }
  return candidate
}

export function CustomObjectsWorkspace({
  objects,
  canManage,
  onCreate,
  onUpdate,
}: CustomObjectsWorkspaceProps) {
  const [selectedId, setSelectedId] = useState(objects[0]?.id ?? '')
  const [fieldDrafts, setFieldDrafts] = useState<Record<string, CustomObjectField[]>>({})
  const [fieldSearch, setFieldSearch] = useState('')
  const [newOpen, setNewOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [draft, setDraft] = useState({ key: '', name: '', description: '' })

  const selected = objects.find((object) => object.id === selectedId) ?? objects[0]
  const fields = selected ? fieldDrafts[selected.id] ?? selected.fields : []
  const fieldNeedle = fieldSearch.trim().toLowerCase()
  const visibleFields = fields.map((field, index) => ({ field, index })).filter(({ field }) =>
    !fieldNeedle || `${field.label} ${field.key} ${field.fieldType}`.toLowerCase().includes(fieldNeedle),
  )

  function setSelectedFields(update: (current: CustomObjectField[]) => CustomObjectField[]) {
    if (!selected) return
    setFieldDrafts((current) => ({
      ...current,
      [selected.id]: update(current[selected.id] ?? selected.fields),
    }))
  }

  function addField(type: TicketFieldType, label: string) {
    if (!canManage) return
    setSelectedFields((current) => [
      ...current,
      { key: fieldKey(type, current), label, fieldType: type, required: false, options: [] },
    ])
    setNotice('Field added. Save the schema to publish it.')
  }

  function updateField(index: number, patch: Partial<CustomObjectField>) {
    setSelectedFields((current) => current.map((field, position) =>
      position === index ? { ...field, ...patch } : field,
    ))
  }

  async function saveSchema() {
    if (!selected || busy) return
    setBusy(true)
    setError('')
    try {
      if (await onUpdate(selected.id, { fields })) {
        setFieldDrafts((current) => {
          const next = { ...current }
          delete next[selected.id]
          return next
        })
        setNotice('Custom object schema saved.')
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The schema could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  async function toggleObject() {
    if (!selected || busy) return
    setBusy(true)
    setError('')
    try {
      if (await onUpdate(selected.id, { active: !selected.active })) {
        setNotice(`${selected.name} ${selected.active ? 'paused' : 'activated'}.`)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The object could not be updated.')
    } finally {
      setBusy(false)
    }
  }

  async function createObject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const created = await onCreate({
        key: draft.key.trim().toLowerCase(),
        name: draft.name.trim(),
        description: draft.description.trim(),
        fields: [],
      })
      if (created) {
        setDraft({ key: '', name: '', description: '' })
        setNewOpen(false)
        setNotice('Custom object created.')
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The object could not be created.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="custom-objects-workspace" aria-label="Custom Objects workspace">
      <header>
        <div>
          <DatabaseZap size={18} />
          <span>
            <strong>{selected?.name ?? 'Custom Objects'}</strong>
            <small>{selected?.description || 'Create structured records for support workflows'}</small>
          </span>
        </div>
        <label>
          <span className="sr-only">Custom object</span>
          <select value={selected?.id ?? ''} onChange={(event) => setSelectedId(event.target.value)}>
            {objects.map((object) => <option key={object.id} value={object.id}>{object.name}</option>)}
          </select>
        </label>
        <button type="button" className="primary-action" onClick={() => setNewOpen(true)} disabled={!canManage}>
          <Plus size={14} /> New object
        </button>
      </header>

      {notice ? <p className="custom-object-notice" role="status">{notice}</p> : null}
      {error ? <p className="custom-object-notice error" role="alert">{error}</p> : null}

      {selected ? (
        <div className="custom-object-builder">
          <aside aria-label="Field types">
            <strong>Field types</strong>
            <small>Select a field type to add it</small>
            {fieldTypes.map(({ type, label, icon: Icon }) => (
              <button key={type} type="button" onClick={() => addField(type, label)} disabled={!canManage}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </aside>

          <main>
            <div className="custom-object-toolbar">
              <span><strong>Fields</strong><small>{fields.length} fields</small></span>
              <label><Search size={14} /><input aria-label="Search fields" value={fieldSearch} onChange={(event) => setFieldSearch(event.target.value)} placeholder="Search fields" /></label>
              <button type="button" onClick={() => void toggleObject()} disabled={!canManage || busy}>
                {selected.active ? 'Pause object' : 'Activate object'}
              </button>
              <button type="button" className="primary-action" onClick={() => void saveSchema()} disabled={!canManage || busy}>Save schema</button>
            </div>
            <div className="custom-object-field-list">
              {visibleFields.map(({ field, index }) => (
                <article key={`${field.key}-${index}`}>
                  <GripVertical size={14} aria-hidden="true" />
                  <span className="custom-field-type">{fieldTypes.find((item) => item.type === field.fieldType)?.label ?? field.fieldType}</span>
                  <label><span className="sr-only">Field label</span><input value={field.label} onChange={(event) => updateField(index, { label: event.target.value })} disabled={!canManage} /></label>
                  <code>{field.key}</code>
                  <label className="custom-field-required"><input type="checkbox" checked={field.required} onChange={(event) => updateField(index, { required: event.target.checked })} disabled={!canManage} /> Required</label>
                  <button type="button" className="icon-button" aria-label={`Remove ${field.label}`} onClick={() => setSelectedFields((current) => current.filter((_, position) => position !== index))} disabled={!canManage}><Trash2 size={14} /></button>
                </article>
              ))}
              {visibleFields.length === 0 ? <div className="custom-object-empty"><DatabaseZap size={24} /><strong>No matching fields</strong><span>Add a field type or change the search.</span></div> : null}
            </div>
          </main>
        </div>
      ) : (
        <div className="custom-object-empty"><DatabaseZap size={28} /><strong>No custom objects</strong><span>Create the first schema for this market.</span><button type="button" className="primary-action" onClick={() => setNewOpen(true)} disabled={!canManage}><Plus size={14} /> New object</button></div>
      )}

      {newOpen ? (
        <div className="custom-object-modal" role="presentation" onMouseDown={() => setNewOpen(false)}>
          <form aria-label="New custom object" onSubmit={(event) => void createObject(event)} onMouseDown={(event) => event.stopPropagation()}>
            <header><div><span>Custom Objects</span><h2>New object</h2></div><button type="button" className="icon-button" aria-label="Close new object" onClick={() => setNewOpen(false)}><X size={16} /></button></header>
            <div>
              <label><span>Name</span><input required value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></label>
              <label><span>Key</span><input required pattern="[a-z][a-z0-9_]{1,63}" value={draft.key} onChange={(event) => setDraft((current) => ({ ...current, key: event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') }))} /></label>
              <label><span>Description</span><textarea rows={4} value={draft.description} onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} /></label>
            </div>
            <footer><button type="button" onClick={() => setNewOpen(false)}>Cancel</button><button type="submit" className="primary-action" disabled={busy || draft.name.trim().length < 1 || !/^[a-z][a-z0-9_]{1,63}$/.test(draft.key)}>Create object</button></footer>
          </form>
        </div>
      ) : null}
    </section>
  )
}
