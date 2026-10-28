import { ConnectionError } from '@/components/ConnectionError'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { useLocalResource } from '@/hooks/useLocalResource'
import { listReviews } from '@/services/api'

export function ReviewsPage() {
  const reviews = useLocalResource(listReviews)

  return (
    <>
      <PageHeader
        title="Reviews"
        description="Stored review runs from the local database. Starting a review is not available in this build."
      />
      {reviews.state.status === 'loading' && <p>Reading the local database…</p>}
      {reviews.state.status === 'error' && (
        <ConnectionError message={reviews.state.message} onRetry={reviews.reload} />
      )}
      {reviews.state.status === 'ready' && reviews.state.data.length === 0 && (
        <EmptyState
          title="No reviews stored"
          body="The local database has no review rows. DevPilot does not create sample findings. A review will appear here only after you explicitly start one in a later build."
        />
      )}
      {reviews.state.status === 'ready' && reviews.state.data.length > 0 && (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {reviews.state.data.map((review) => (
            <li key={review.id} className="px-5 py-4">
              <p className="font-medium">{review.status}</p>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {review.model} · {review.finding_count} stored findings
              </p>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
