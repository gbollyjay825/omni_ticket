import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, DatabaseZap, RefreshCw, ShieldCheck, XCircle } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { BackendSession } from '../../backend'
import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'

type ImportRun = components['schemas']['ImportRunResponse']
type ImportCursor = components['schemas']['ImportCursorResponse']
type ImportReconciliation = components['schemas']['ImportReconciliationResponse']
type ReconciliationManifestRequest = components['schemas']['ReconciliationManifestRequest']

type ProviderName = 'freshdesk' | 'freshchat'

interface ReadinessCheck {
  key: string
  label: string
  passed: boolean
  detail: string
  provider?: string
}

interface ProviderResult {
  verified: boolean
  required_entities: string[]
  differences: Record<string, number>
  checks: ReadinessCheck[]
}

interface CutoverStatus {
  status: 'approved' | 'revoked'
  decided_by: string
  decided_at: string
  rollback_until: string | null
  snapshot_current: boolean
  rollback_active: boolean
  reason: string
}

interface ManifestEntityDraft {
  sourceCount: string
  sourceChecksum: string
  sampleSize: string
  sampleFailures: string
  missingAttachments: string
}

const requiredEntities: Record<ProviderName, string[]> = {
  freshdesk: ['contact', 'ticket', 'conversation'],
  freshchat: ['user', 'conversation', 'message'],
}

interface ImportControlPlaneData {
  runs: ImportRun[]
  cursors: ImportCursor[]
  reconciliation: ImportReconciliation
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'detail' in error && typeof error.detail === 'string') {
    return error.detail
  }
  return 'Migration status is unavailable.'
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return 'Not recorded'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

function counterTotal(value: ImportRun['statistics']) {
  let total = 0
  for (const item of Object.values(value ?? {})) {
    total += typeof item === 'number'
      ? item
      : Object.values(item).reduce((subtotal, count) => subtotal + count, 0)
  }
  return total
}

function reconciliationTotal(provider: Record<string, number> | undefined) {
  return Object.values(provider ?? {}).reduce((total, count) => total + count, 0)
}

function localDateTimeValue() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function numericValue(value: string) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0
}

export function ImportControlPlane({ session }: { session: BackendSession | null }) {
  const client = useMemo(() => createOmniApiClient(session), [session])
  const [manifestProvider, setManifestProvider] = useState<ProviderName | null>(null)
  const [manifestSnapshotAt, setManifestSnapshotAt] = useState(localDateTimeValue)
  const [manifestDraft, setManifestDraft] = useState<Record<string, ManifestEntityDraft>>({})
  const [cutoverReason, setCutoverReason] = useState('')
  const query = useQuery({
    queryKey: ['import-control-plane', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<ImportControlPlaneData> => {
      const [runsResponse, cursorsResponse, reconciliationResponse] = await Promise.all([
        client.GET('/api/v1/imports/runs', { params: { query: { limit: 50 } } }),
        client.GET('/api/v1/imports/cursors'),
        client.GET('/api/v1/imports/reconciliation'),
      ])
      const error = runsResponse.error ?? cursorsResponse.error ?? reconciliationResponse.error
      if (error) throw error
      if (!runsResponse.data || !cursorsResponse.data || !reconciliationResponse.data) {
        throw new Error('Migration status returned an incomplete response.')
      }
      return {
        runs: runsResponse.data,
        cursors: cursorsResponse.data,
        reconciliation: reconciliationResponse.data,
      }
    },
  })

  const manifestMutation = useMutation({
    mutationFn: async (body: ReconciliationManifestRequest) => {
      const response = await client.POST('/api/v1/imports/reconciliation/manifests', { body })
      if (response.error) throw response.error
      if (!response.data) throw new Error('The source manifest was not recorded.')
      return response.data
    },
    onSuccess: () => {
      setManifestProvider(null)
      void query.refetch()
    },
  })

  const cutoverMutation = useMutation({
    mutationFn: async ({ action, reason }: { action: 'approve' | 'revoke'; reason: string }) => {
      const response = action === 'approve'
        ? await client.POST('/api/v1/imports/cutover/approve', { body: { reason } })
        : await client.POST('/api/v1/imports/cutover/revoke', { body: { reason } })
      if (response.error) throw response.error
      if (!response.data) throw new Error(`Cutover ${action} returned no status.`)
      return response.data
    },
    onSuccess: () => {
      setCutoverReason('')
      void query.refetch()
    },
  })

  const runs = query.data?.runs ?? []
  const cursors = query.data?.cursors ?? []
  const reconciliation = query.data?.reconciliation
  const providerResults = (reconciliation?.provider_results ?? {}) as unknown as Record<string, ProviderResult>
  const readiness = reconciliation?.readiness as { ready?: boolean; checks?: ReadinessCheck[] } | undefined
  const cutover = reconciliation?.cutover as unknown as CutoverStatus | null | undefined
  const completedRuns = runs.filter((run) => run.status === 'completed').length
  const failedRuns = runs.filter((run) => run.status === 'failed').length
  const mappedRecords = Object.values(reconciliation?.providers ?? {}).reduce(
    (total, provider) => total + reconciliationTotal(provider),
    0,
  )
  const releaseReady = readiness?.ready === true
  const approvedCutover = cutover?.status === 'approved'

  function openManifest(provider: ProviderName) {
    const manifests = reconciliation?.source_manifests?.[provider] ?? {}
    setManifestDraft(Object.fromEntries(requiredEntities[provider].map((entityType) => {
      const source = manifests[entityType]
      return [entityType, {
        sourceCount: String(source?.source_count ?? ''),
        sourceChecksum: String(source?.source_checksum ?? ''),
        sampleSize: String(source?.sample_size ?? ''),
        sampleFailures: String(source?.sample_failures ?? ''),
        missingAttachments: String(source?.missing_attachments ?? ''),
      }]
    })))
    setManifestSnapshotAt(localDateTimeValue())
    setManifestProvider(provider)
  }

  function updateManifestEntity(entityType: string, field: keyof ManifestEntityDraft, value: string) {
    setManifestDraft((current) => ({
      ...current,
      [entityType]: { ...current[entityType], [field]: value },
    }))
  }

  function saveManifest() {
    if (!manifestProvider || !manifestSnapshotAt) return
    void manifestMutation.mutateAsync({
      provider: manifestProvider,
      source_snapshot_at: new Date(manifestSnapshotAt).toISOString(),
      entities: requiredEntities[manifestProvider].map((entityType) => {
        const draft = manifestDraft[entityType]
        return {
          entity_type: entityType,
          source_count: numericValue(draft?.sourceCount ?? ''),
          source_checksum: draft?.sourceChecksum ?? '',
          sample_size: numericValue(draft?.sampleSize ?? ''),
          sample_failures: numericValue(draft?.sampleFailures ?? ''),
          missing_attachments: numericValue(draft?.missingAttachments ?? ''),
          notes: '',
        }
      }),
    })
  }

  return (
    <div data-setup-panel="migration" className="automation-settings-panel import-control-plane" id="migration-controls">
      <div className="panel-head compact">
        <div>
          <span>Data migration</span>
          <h2>Freshworks reconciliation</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          onClick={() => void query.refetch()}
          disabled={!session || query.isFetching}
          aria-label="Refresh migration status"
          title="Refresh migration status"
        >
          <RefreshCw size={16} className={query.isFetching ? 'spin-icon' : undefined} />
        </button>
      </div>

      {query.error ? (
        <div className="import-status-message error" role="alert">
          <AlertTriangle size={16} />
          <span>{errorMessage(query.error)}</span>
        </div>
      ) : null}

      <div className="import-summary" aria-label="Migration summary">
        <article>
          <span>Mapped records</span>
          <strong>{mappedRecords.toLocaleString()}</strong>
        </article>
        <article>
          <span>Completed runs</span>
          <strong>{completedRuns}</strong>
        </article>
        <article>
          <span>Failed runs</span>
          <strong>{failedRuns}</strong>
        </article>
        <article>
          <span>Release gate</span>
          <strong>{releaseReady ? 'Ready' : 'Blocked'}</strong>
        </article>
      </div>

      <div className="import-provider-list" aria-label="Source reconciliation">
        {['freshdesk', 'freshchat'].map((provider) => {
          const providerRuns = runs.filter((run) => run.provider === provider)
          const latestRun = providerRuns[0]
          const mapped = reconciliationTotal(reconciliation?.providers?.[provider])
          const result = providerResults[provider]
          const typedProvider = provider as ProviderName
          return (
            <article key={provider}>
              <DatabaseZap size={17} />
              <div>
                <strong>{provider === 'freshdesk' ? 'Freshdesk' : 'Freshchat'}</strong>
                <span>{mapped.toLocaleString()} mapped records</span>
              </div>
              <div>
                <strong className={result?.verified ? 'import-verified' : 'import-blocked'}>
                  {result?.verified ? 'Verified' : 'Blocked'}
                </strong>
                <span>{latestRun ? `${latestRun.status} · ${formatTimestamp(latestRun.finished_at ?? latestRun.started_at)}` : 'No run recorded'}</span>
                <button type="button" className="secondary-action" onClick={() => openManifest(typedProvider)}>
                  Source totals
                </button>
              </div>
            </article>
          )
        })}
      </div>

      {manifestProvider ? (
        <section className="import-manifest-form" aria-labelledby="source-manifest-heading">
          <header>
            <div>
              <span>Source evidence</span>
              <h3 id="source-manifest-heading">{manifestProvider} reconciliation manifest</h3>
            </div>
            <button type="button" className="icon-button" aria-label="Close source manifest" title="Close source manifest" onClick={() => setManifestProvider(null)}>
              <XCircle size={16} />
            </button>
          </header>
          <label>
            <span>Source snapshot</span>
            <input type="datetime-local" value={manifestSnapshotAt} onChange={(event) => setManifestSnapshotAt(event.target.value)} />
          </label>
          <div className="import-manifest-table">
            <div className="import-manifest-row header" aria-hidden="true">
              <span>Entity</span><span>Source total</span><span>Sampled</span><span>Failures</span><span>Missing files</span><span>Checksum</span>
            </div>
            {requiredEntities[manifestProvider].map((entityType) => {
              const draft = manifestDraft[entityType]
              return (
                <div className="import-manifest-row" key={entityType}>
                  <strong>{entityType}</strong>
                  <input aria-label={`${entityType} source total`} type="number" min="0" value={draft?.sourceCount ?? ''} onChange={(event) => updateManifestEntity(entityType, 'sourceCount', event.target.value)} />
                  <input aria-label={`${entityType} sample size`} type="number" min="0" value={draft?.sampleSize ?? ''} onChange={(event) => updateManifestEntity(entityType, 'sampleSize', event.target.value)} />
                  <input aria-label={`${entityType} sample failures`} type="number" min="0" value={draft?.sampleFailures ?? ''} onChange={(event) => updateManifestEntity(entityType, 'sampleFailures', event.target.value)} />
                  <input aria-label={`${entityType} missing attachments`} type="number" min="0" value={draft?.missingAttachments ?? ''} onChange={(event) => updateManifestEntity(entityType, 'missingAttachments', event.target.value)} />
                  <input aria-label={`${entityType} source checksum`} value={draft?.sourceChecksum ?? ''} placeholder="SHA-256" onChange={(event) => updateManifestEntity(entityType, 'sourceChecksum', event.target.value)} />
                </div>
              )
            })}
          </div>
          {manifestMutation.error ? <p className="import-status-message error" role="alert">{errorMessage(manifestMutation.error)}</p> : null}
          <div className="import-form-actions">
            <button type="button" className="secondary-action" onClick={() => setManifestProvider(null)}>Cancel</button>
            <button type="button" className="primary-action" disabled={manifestMutation.isPending || !manifestSnapshotAt} onClick={saveManifest}>
              {manifestMutation.isPending ? 'Recording…' : 'Record evidence'}
            </button>
          </div>
        </section>
      ) : null}

      <section className={`import-release-gate ${releaseReady ? 'ready' : 'blocked'}`} aria-labelledby="release-gate-heading">
        <header>
          <div>
            {releaseReady ? <ShieldCheck size={18} /> : <AlertTriangle size={18} />}
            <div>
              <span>Cutover control</span>
              <h3 id="release-gate-heading">{releaseReady ? 'Evidence complete' : 'Release remains blocked'}</h3>
            </div>
          </div>
          {cutover ? <span className={`import-cutover-status ${cutover.status}`}>{cutover.status}</span> : null}
        </header>
        <div className="import-gate-providers">
          {(Object.keys(requiredEntities) as ProviderName[]).map((provider) => {
            const result = providerResults[provider]
            const failedChecks = result?.checks?.filter((check) => !check.passed) ?? []
            return (
              <article key={provider}>
                <strong>{provider}</strong>
                <span>{result?.verified ? '6 of 6 checks passed' : `${failedChecks.length || 6} check(s) need evidence`}</span>
                <details>
                  <summary>Review checks</summary>
                  <div className="import-check-list">
                    {(result?.checks ?? []).map((check) => (
                      <div key={check.key} className={check.passed ? 'passed' : 'failed'}>
                        {check.passed ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                        <span><strong>{check.label}</strong>{check.detail}</span>
                      </div>
                    ))}
                  </div>
                </details>
              </article>
            )
          })}
        </div>
        {cutover ? (
          <p className="import-cutover-detail">
            {cutover.status === 'approved' ? `Approved by ${cutover.decided_by}. Rollback window ends ${formatTimestamp(cutover.rollback_until)}.` : `Revoked by ${cutover.decided_by}.`}
            {!cutover.snapshot_current && cutover.status === 'approved' ? ' The evidence changed after approval; approve a new snapshot before routing.' : ''}
          </p>
        ) : null}
        <label className="import-cutover-reason">
          <span>Decision reason</span>
          <input value={cutoverReason} onChange={(event) => setCutoverReason(event.target.value)} placeholder="Reference the approved migration and rollback decision" />
        </label>
        {cutoverMutation.error ? <p className="import-status-message error" role="alert">{errorMessage(cutoverMutation.error)}</p> : null}
        <div className="import-form-actions">
          {approvedCutover ? (
            <button type="button" className="secondary-action danger-outline-action" disabled={cutoverMutation.isPending || cutoverReason.trim().length < 10} onClick={() => cutoverMutation.mutate({ action: 'revoke', reason: cutoverReason.trim() })}>
              Revoke approval
            </button>
          ) : (
            <button type="button" className="primary-action" disabled={!releaseReady || cutoverMutation.isPending || cutoverReason.trim().length < 10} onClick={() => cutoverMutation.mutate({ action: 'approve', reason: cutoverReason.trim() })}>
              Approve cutover
            </button>
          )}
        </div>
      </section>

      <section className="import-table-section" aria-labelledby="import-runs-heading">
        <header>
          <h3 id="import-runs-heading">Run history</h3>
          <span>{runs.length} recorded</span>
        </header>
        {runs.length ? (
          <div className="import-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Mode</th>
                  <th>Status</th>
                  <th>Records</th>
                  <th>Finished</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>{run.provider}</td>
                    <td>{run.dry_run ? `${run.mode} dry run` : run.mode}</td>
                    <td>
                      <span className={`import-run-status ${run.status}`}>
                        {run.status === 'completed' ? <CheckCircle2 size={13} /> : null}
                        {run.status === 'failed' ? <AlertTriangle size={13} /> : null}
                        {run.status}
                      </span>
                    </td>
                    <td>{counterTotal(run.statistics).toLocaleString()}</td>
                    <td>{formatTimestamp(run.finished_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="import-empty-state">No migration runs recorded for this market.</p>
        )}
      </section>

      <section className="import-table-section" aria-labelledby="import-cursors-heading">
        <header>
          <h3 id="import-cursors-heading">Durable checkpoints</h3>
          <span>{cursors.length} active</span>
        </header>
        {cursors.length ? (
          <div className="import-checkpoint-list">
            {cursors.map((cursor) => (
              <article key={cursor.id}>
                <div>
                  <strong>{cursor.provider}</strong>
                  <span>{cursor.resource}</span>
                </div>
                <time dateTime={cursor.checkpoint_at}>{formatTimestamp(cursor.checkpoint_at)}</time>
              </article>
            ))}
          </div>
        ) : (
          <p className="import-empty-state">No migration checkpoints recorded for this market.</p>
        )}
      </section>
    </div>
  )
}
