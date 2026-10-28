import { Link } from 'react-router-dom'

import { ConnectionError } from '@/components/ConnectionError'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { useLocalResource } from '@/hooks/useLocalResource'
import { listReleaseReports } from '@/services/api'

const READINESS_LABEL = {
  blocked: 'Blocked',
  needs_review: 'Needs review',
  ready_for_human_approval: 'Ready for human approval',
} as const

export function ReleasesPage() {
  const reports = useLocalResource(listReleaseReports)

  return (
    <>
      <PageHeader
        phase="Phase 4"
        title="Release reports"
        description="A stored assessment combines the review, quality checks, and human decisions. Saving a report does not approve the release."
      />
      <Button asChild className="mb-6">
        <Link to="/releases/new">New release report</Link>
      </Button>
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
              <Link to={`/releases/${report.id}`} className="font-medium hover:underline">
                {report.title}
              </Link>
              <p className="mt-1 text-xs text-muted-foreground">
                {report.readiness ? READINESS_LABEL[report.readiness] : 'No readiness stored'}
                {' · '}
                Stored as {report.status}
              </p>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
