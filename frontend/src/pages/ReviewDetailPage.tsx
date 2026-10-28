import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { ConnectionError } from '@/components/ConnectionError'
import { DiffView } from '@/components/DiffView'
import { PageHeader } from '@/components/PageHeader'
import { QualityResultList } from '@/components/QualityResultList'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  cancelReview,
  listQualityChecks,
  readFileDiff,
  readReview,
  type DiffScope,
  type FileDiff,
  type QualityCheckRecord,
  type ReviewDetail,
  type ReviewFinding,
} from '@/services/api'

const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'] as const

const CATEGORY_LABELS: Record<string, string> = {
  functional: 'Functional defects and regressions',
  security: 'Security vulnerabilities',
  magento_di: 'Magento dependency injection, plugins, observers, and preferences',
  service_contracts: 'Service contracts, repository usage, and API compatibility',
  store_scope: 'Store scope, multi-store behavior, and configuration',
  sql: 'SQL safety and database performance',
  cache_indexers: 'Cache invalidation and indexer implications',
  validation_escaping: 'Input validation, authorization, and output escaping',
  performance: 'Performance and maintainability',
  tests: 'Missing or insufficient automated tests',
}

export function ReviewDetailPage() {
  const { reviewId = '' } = useParams()
  const [review, setReview] = useState<ReviewDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [severity, setSeverity] = useState('all')
  const [category, setCategory] = useState('all')
  const [active, setActive] = useState<ReviewFinding | null>(null)
  const [diff, setDiff] = useState<FileDiff | null>(null)
  const [diffError, setDiffError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const next = await readReview(reviewId)
      setReview(next)
      setError(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The review could not be read.')
    }
  }, [reviewId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!review || (review.status !== 'running' && review.status !== 'pending')) {
      return
    }
    const timer = window.setInterval(() => {
      void load()
    }, 2000)
    return () => window.clearInterval(timer)
  }, [review, load])

  async function openFinding(finding: ReviewFinding) {
    setActive(finding)
    setDiff(null)
    setDiffError(null)
    if (!review || !isScope(finding.scope)) {
      setDiffError('This finding has no diff scope to open.')
      return
    }
    try {
      setDiff(await readFileDiff(review.project_id, finding.scope, finding.file_path, review.base_ref))
    } catch (caught) {
      setDiffError(caught instanceof Error ? caught.message : 'The diff could not be read.')
    }
  }

  const findings =
    review?.findings.filter((finding) => {
      if (severity !== 'all' && finding.severity !== severity) {
        return false
      }
      return category === 'all' || finding.category === category
    }) ?? []

  return (
    <>
      <PageHeader
        phase="Phase 2"
        title="Review"
        description="AI suggestions from the local model. They are not test failures, and they are not guaranteed to be correct."
      />
      {error && <ConnectionError message={error} onRetry={() => void load()} />}
      {!review && !error && <p>Reading the local review…</p>}
      {review && (
        <div className="space-y-6">
          <section className="rounded-lg border border-border bg-card px-5 py-4 text-sm">
            <p>
              Model <span className="font-mono">{review.model}</span>
              {review.temperature !== null ? ` · temperature ${review.temperature}` : ''}
              {review.keep_alive ? ` · keep-alive ${review.keep_alive}` : ''}
            </p>
            <p className="mt-1">
              Scope {review.base_ref ?? 'working tree'}
              {review.head_ref ? ` … ${review.head_ref}` : ''}
            </p>
            <p className="mt-2">{review.summary}</p>
            {(review.status === 'running' || review.status === 'pending') && (
              <p className="mt-3">
                Progress {review.chunks_completed} of {review.chunks_total} chunks.
              </p>
            )}
            {review.error_message && (
              <p role="alert" className="mt-3 text-destructive">
                {review.error_message}
              </p>
            )}
            {review.status === 'running' && (
              <Button className="mt-3" type="button" variant="outline" onClick={() => void cancelReview(reviewId).then(() => load())}>
                Cancel review
              </Button>
            )}
          </section>
          <section>
            <h2 className="font-serif text-2xl">Scope</h2>
            <p className="mt-2 text-sm">
              {review.files_reviewed} file(s) reviewed. {review.files_skipped} file(s) skipped.
            </p>
            {review.reviewed_files.length > 0 && (
              <ul className="mt-2 font-mono text-xs">
                {review.reviewed_files.map((path) => (
                  <li key={path}>{path}</li>
                ))}
              </ul>
            )}
            {review.skipped_files.length > 0 && (
              <ul className="mt-3 text-sm text-muted-foreground">
                {review.skipped_files.map((file) => (
                  <li key={`${file.path}-${file.reason}`}>
                    {file.path}: {file.reason}
                  </li>
                ))}
              </ul>
            )}
            {review.limitations.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-medium">Analysis limitations</h3>
                <ul className="mt-2 list-disc pl-5 text-sm">
                  {review.limitations.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
          <section>
            <h2 className="font-serif text-2xl">AI suggestions</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6">
              These comments came from the model. They are not deterministic test failures. A person
              needs to verify each one against the diff.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <select
                aria-label="Severity"
                className="rounded-md border border-input bg-card px-3 py-2 text-sm"
                value={severity}
                onChange={(event) => setSeverity(event.target.value)}
              >
                <option value="all">All severities</option>
                {SEVERITIES.map((item) => (
                  <option key={item} value={item}>
                    {item === 'info' ? 'informational' : item}
                  </option>
                ))}
              </select>
              <select
                aria-label="Category"
                className="rounded-md border border-input bg-card px-3 py-2 text-sm"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              >
                <option value="all">All categories</option>
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            {findings.length === 0 && (
              <p className="mt-4 text-sm text-muted-foreground">No AI suggestions in this filter.</p>
            )}
            <ul className="mt-4 divide-y divide-border">
              {findings.map((finding) => (
                <li key={finding.id} className="py-3">
                  <button
                    type="button"
                    className="text-left"
                    onClick={() => void openFinding(finding)}
                  >
                    <span className="font-medium">{finding.title}</span>
                    <span className="ml-2 font-mono text-xs text-muted-foreground">
                      {finding.file_path}:{finding.start_line}
                    </span>
                  </button>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge>{finding.severity === 'info' ? 'informational' : finding.severity}</Badge>
                    <Badge>{CATEGORY_LABELS[finding.category] ?? finding.category}</Badge>
                    <Badge>AI suggestion</Badge>
                    <Badge>
                      {finding.needs_human_verification ? 'Needs human verification' : 'Checked'}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          </section>
          {active && (
            <section className="rounded-lg border border-border bg-card px-5 py-4">
              <h2 className="font-serif text-2xl">{active.title}</h2>
              <p className="mt-2 text-sm">{active.explanation}</p>
              <p className="mt-3 text-sm">
                <span className="font-medium">Evidence from the diff. </span>
                {active.evidence}
              </p>
              <p className="mt-2 text-sm">
                <span className="font-medium">Remediation. </span>
                {active.remediation}
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                Confidence {active.confidence}. This is an AI suggestion
                {active.evidence_checked ? ' whose quote was found in the reviewed diff' : ''}. It
                is not a test failure.
              </p>
            </section>
          )}
          {diffError && <p className="text-sm text-destructive">{diffError}</p>}
          {diff && (
            <DiffView
              lines={diff.lines}
              language={diff.language}
              binary={diff.binary}
              truncated={diff.truncated}
              skipped={diff.skipped}
            />
          )}
          <CommandResults projectId={review.project_id} reviewId={review.id} />
        </div>
      )}
    </>
  )
}

function CommandResults({ projectId, reviewId }: { projectId: string; reviewId: string }) {
  const [runs, setRuns] = useState<QualityCheckRecord[] | null>(null)

  useEffect(() => {
    let cancelled = false
    void listQualityChecks(projectId)
      .then((items) => {
        if (!cancelled) {
          setRuns(items.filter((item) => item.review_id === reviewId))
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRuns([])
        }
      })
    return () => {
      cancelled = true
    }
  }, [projectId, reviewId])

  return (
    <section>
      <h2 className="font-serif text-2xl">Deterministic command results</h2>
      <p className="mb-4 mt-2 max-w-3xl text-sm leading-6">
        These rows are exit results from commands you confirmed on the quality-check page. They are
        not AI suggestions.
      </p>
      {runs && <QualityResultList runs={runs} />}
    </section>
  )
}

function isScope(value: string): value is DiffScope {
  return value === 'staged' || value === 'unstaged' || value === 'committed' || value === 'untracked'
}
