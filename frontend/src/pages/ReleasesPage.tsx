import { ConnectionError } from '@/components/ConnectionError'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { useLocalResource } from '@/hooks/useLocalResource'
import { listReleaseReports } from '@/services/api'

export function ReleasesPage() {
  const reports = useLocalResource(listReleaseReports)

  return (
    <>
      <PageHeader
        title="Release reports"
        description="Release reports stored on this machine. Report generation is not part of this build."
      />
      {reports.state.status === 'loading' && <p>Reading the local database…</p>}
      {reports.state.status === 'error' && (
        <ConnectionError message={reports.state.message} onRetry={reports.reload} />
      )}
      {reports.state.status === 'ready' && reports.state.data.length === 0 && (
        <EmptyState
          title="No release reports stored"
          body="The local database has no release-report rows. DevPilot does not generate a sample report."
        />
      )}
      {reports.state.status === 'ready' && reports.state.data.length > 0 && (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {reports.state.data.map((report) => (
            <li key={report.id} className="px-5 py-4">
              <p className="font-medium">{report.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">{report.status}</p>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
