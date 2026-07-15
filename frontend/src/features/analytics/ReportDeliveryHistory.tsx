import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Clock3, Play, RefreshCw, X } from 'lucide-react'
import { useMemo, useState } from 'react'

import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'
import type { BackendSession } from '../../backend'

type ReportDelivery = components['schemas']['ReportDeliveryResponse']
type ReportDeliveryRun = components['schemas']['ReportDeliveryRunResponse']

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'detail' in error && typeof error.detail === 'string') {
    return error.detail
  }
  return 'Scheduled report delivery status is unavailable.'
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

function statusIcon(status: string) {
  if (status === 'sent') return <CheckCircle2 size={14} />
  if (status === 'blocked' || status === 'dead_lettered') return <AlertTriangle size={14} />
  return <Clock3 size={14} />
}

export function ReportDeliveryHistory({ session }: { session: BackendSession | null }) {
  const client = useMemo(() => createOmniApiClient(session), [session])
  const queryClient = useQueryClient()
  const [confirmationOpen, setConfirmationOpen] = useState(false)
  const [lastRun, setLastRun] = useState<ReportDeliveryRun | null>(null)
  const queryKey = ['report-deliveries', session?.market.id]
  const query = useQuery({
    queryKey,
    enabled: Boolean(session),
    queryFn: async (): Promise<ReportDelivery[]> => {
      const response = await client.GET('/api/v1/reports/deliveries', {
        params: { query: { limit: 100 } },
      })
      if (response.error) throw response.error
      return response.data ?? []
    },
  })
  const processDue = useMutation({
    mutationFn: async (): Promise<ReportDeliveryRun> => {
      const response = await client.POST('/api/v1/reports/deliveries/process-due')
      if (response.error) throw response.error
      if (!response.data) throw new Error('Report delivery returned an empty response.')
      return response.data
    },
    onSuccess: async (result) => {
      setLastRun(result)
      setConfirmationOpen(false)
      await queryClient.invalidateQueries({ queryKey })
    },
  })

  const deliveries = query.data ?? []
  const pending = deliveries.filter((item) => ['queued', 'retrying', 'blocked'].includes(item.status)).length

  return (
    <section className="report-delivery-history" aria-labelledby="report-delivery-heading">
      <header>
        <div>
          <span>Delivery log</span>
          <h3 id="report-delivery-heading">Scheduled export history</h3>
        </div>
        <div className="report-delivery-actions">
          <button
            type="button"
            className="icon-button"
            onClick={() => void query.refetch()}
            disabled={!session || query.isFetching}
            aria-label="Refresh scheduled export history"
            title="Refresh scheduled export history"
          >
            <RefreshCw size={15} className={query.isFetching ? 'spin-icon' : undefined} />
          </button>
          {confirmationOpen ? (
            <>
              <button
                type="button"
                className="danger-outline-action"
                onClick={() => processDue.mutate()}
                disabled={processDue.isPending}
              >
                <Play size={14} />
                {processDue.isPending ? 'Processing' : 'Confirm process due'}
              </button>
              <button
                type="button"
                className="icon-button"
                onClick={() => setConfirmationOpen(false)}
                disabled={processDue.isPending}
                aria-label="Cancel scheduled export processing"
                title="Cancel"
              >
                <X size={15} />
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmationOpen(true)}
              disabled={!session || processDue.isPending}
            >
              <Play size={14} />
              Process due
            </button>
          )}
        </div>
      </header>

      {confirmationOpen ? (
        <p className="report-delivery-confirmation" role="status">
          This queues the current period once per active schedule and sends any due exports when SMTP is configured.
        </p>
      ) : null}
      {query.error || processDue.error ? (
        <div className="report-delivery-message error" role="alert">
          <AlertTriangle size={15} />
          {errorMessage(query.error ?? processDue.error)}
        </div>
      ) : null}
      {lastRun ? (
        <div className="report-delivery-message" role="status">
          <span>{lastRun.sent_ids.length} sent</span>
          <span>{lastRun.blocked_ids.length} blocked</span>
          <span>{lastRun.retrying_ids.length} retrying</span>
          <span>{lastRun.dead_lettered_ids.length} dead-lettered</span>
        </div>
      ) : null}

      <div className="report-delivery-summary">
        <span>{deliveries.length} recorded</span>
        <span>{pending} pending action</span>
      </div>

      {query.isPending ? (
        <p className="report-catalog-state">Loading delivery history...</p>
      ) : deliveries.length ? (
        <div className="report-delivery-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Export</th>
                <th>Period</th>
                <th>Recipients</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Attempts</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {deliveries.map((delivery) => (
                <tr key={delivery.id}>
                  <td>
                    <strong>{delivery.filename}</strong>
                    <span>{delivery.report_type}</span>
                  </td>
                  <td>{delivery.period_key}</td>
                  <td>{delivery.recipients.join(', ')}</td>
                  <td>
                    <span className={`report-delivery-status ${delivery.status}`}>
                      {statusIcon(delivery.status)}
                      {delivery.status.replaceAll('_', ' ')}
                    </span>
                    {delivery.last_error ? <small>{delivery.last_error}</small> : null}
                  </td>
                  <td>{delivery.row_count.toLocaleString()}</td>
                  <td>{delivery.attempts}/{delivery.max_attempts}</td>
                  <td>{formatTimestamp(delivery.sent_at ?? delivery.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="report-catalog-state">No scheduled exports have been processed for this market.</p>
      )}
    </section>
  )
}
