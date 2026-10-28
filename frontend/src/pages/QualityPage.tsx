import { ConnectionError } from '@/components/ConnectionError'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { useLocalResource } from '@/hooks/useLocalResource'
import { listQualityChecks } from '@/services/api'

export function QualityPage() {
  const checks = useLocalResource(listQualityChecks)

  return (
    <>
      <PageHeader
        title="Quality checks"
        description="Quality-check runs stored on this machine. Checks are not executed in this build."
      />
      {checks.state.status === 'loading' && <p>Reading the local database…</p>}
      {checks.state.status === 'error' && (
        <ConnectionError message={checks.state.message} onRetry={checks.reload} />
      )}
      {checks.state.status === 'ready' && checks.state.data.length === 0 && (
        <EmptyState
          title="No quality checks stored"
          body="The local database has no quality-check rows. DevPilot does not fill this page with sample results."
        />
      )}
      {checks.state.status === 'ready' && checks.state.data.length > 0 && (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {checks.state.data.map((check) => (
            <li key={check.id} className="px-5 py-4 text-sm">
              {check.status}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
