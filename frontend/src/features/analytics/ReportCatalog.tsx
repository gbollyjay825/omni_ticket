import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Download, RefreshCw, Star } from 'lucide-react'
import { useMemo } from 'react'

import { createOmniApiClient } from '../../api/client'
import type { components } from '../../api/schema'
import type { BackendReportType, BackendSession } from '../../backend'

type ReportCatalogItem = components['schemas']['ReportCatalogItem']

const reportBadges: Record<BackendReportType, string> = {
  tickets: 'Tickets',
  chat: 'Chat',
  csat: 'CSAT',
  team: 'Team',
  ai: 'AI',
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'detail' in error && typeof error.detail === 'string') {
    return error.detail
  }
  return 'The report catalog is unavailable.'
}

interface ReportCatalogProps {
  session: BackendSession | null
  exporting: BackendReportType | null
  search?: string
  sort?: 'modified' | 'name'
  onExport: (reportType: BackendReportType) => Promise<void>
}

export function ReportCatalog({ session, exporting, search = '', sort = 'modified', onExport }: ReportCatalogProps) {
  const client = useMemo(() => createOmniApiClient(session), [session])
  const query = useQuery({
    queryKey: ['report-catalog', session?.market.id],
    enabled: Boolean(session),
    queryFn: async (): Promise<ReportCatalogItem[]> => {
      const response = await client.GET('/api/v1/reports/catalog')
      if (response.error) throw response.error
      return response.data ?? []
    },
  })
  const reports = useMemo(() => {
    const needle = search.trim().toLowerCase()
    const filtered = (query.data ?? []).filter((report) =>
      !needle || `${report.name} ${report.description} ${report.report_type}`.toLowerCase().includes(needle),
    )
    return sort === 'name'
      ? [...filtered].sort((left, right) => left.name.localeCompare(right.name))
      : filtered
  }, [query.data, search, sort])

  if (query.error) {
    return (
      <div className="report-catalog-state error" role="alert">
        <AlertTriangle size={16} />
        <span>{errorMessage(query.error)}</span>
        <button type="button" onClick={() => void query.refetch()}>
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    )
  }

  if (query.isPending) {
    return <p className="report-catalog-state">Loading reports...</p>
  }

  if (!query.data.length) {
    return (
      <div className="report-catalog-state">
        <span>No reports are configured for this market.</span>
        <button type="button" onClick={() => void query.refetch()}>
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>
    )
  }

  if (!reports.length) {
    return <p className="report-catalog-state">No reports match this search.</p>
  }

  return (
    <div className="analytics-report-list" aria-label="All analytics reports">
      <div className="analytics-report-list-head">
        <span />
        <strong>Name</strong>
        <strong>Type</strong>
        <strong>Export</strong>
      </div>
      {reports.map((report) => (
        <article key={report.id}>
          <Star size={16} aria-hidden="true" />
          <div>
            <a href="#analytics-report-detail">{report.name}</a>
            <span>{report.description}</span>
          </div>
          <em>{reportBadges[report.report_type]}</em>
          <button
            type="button"
            onClick={() => void onExport(report.report_type)}
            disabled={!session || exporting !== null}
            aria-label={`Export ${report.name}`}
          >
            {exporting === report.report_type ? (
              <RefreshCw size={14} className="spin-icon" />
            ) : (
              <Download size={14} />
            )}
            {exporting === report.report_type ? 'Preparing' : 'CSV'}
          </button>
        </article>
      ))}
    </div>
  )
}
