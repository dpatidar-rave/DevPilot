import { Link } from 'react-router-dom'

import { ConnectionError } from '@/components/ConnectionError'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { useLocalResource } from '@/hooks/useLocalResource'
import { listReviews } from '@/services/api'

export function ReviewsPage() {
  const reviews = useLocalResource(listReviews)

  return (
    <>
      <PageHeader
        phase="Phase 2"
        title="Reviews"
        description="Each review is an AI suggestion from the local Ollama model. It is not a test run, and it is not guaranteed to be correct."
      />
      <p className="mb-6 text-sm">
        <Link className="text-primary" to="/reviews/new">
          Start a review
        </Link>
      </p>
      {reviews.state.status === 'loading' && <p>Reading the local database…</p>}
      {reviews.state.status === 'error' && (
        <ConnectionError message={reviews.state.message} onRetry={reviews.reload} />
      )}
      {reviews.state.status === 'ready' && reviews.state.data.length === 0 && (
        <EmptyState
          title="No reviews stored"
          body="The local database has no review rows. DevPilot does not create sample findings. A review appears here only after you start one."
        />
      )}
      {reviews.state.status === 'ready' && reviews.state.data.length > 0 && (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {reviews.state.data.map((review) => (
            <li key={review.id} className="px-5 py-4">
              <Link className="font-medium hover:text-primary" to={`/reviews/${review.id}`}>
                {review.status}
              </Link>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {review.model} · {review.finding_count} AI suggestions
              </p>
              <div className="mt-2">
                <Badge>AI suggestion</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
