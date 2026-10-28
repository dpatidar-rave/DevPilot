import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { PageHeader } from '@/components/PageHeader'
import { ReleaseReportView } from '@/components/ReleaseReportView'
import { Button } from '@/components/ui/button'
import {
  createReleaseReport,
  listProjects,
  listReviews,
  previewRelease,
  saveChecklistDecision,
  saveFindingDecision,
  type ChecklistItem,
  type ChecklistStatus,
  type FindingDisposition,
  type ProjectRecord,
  type ReleaseAssessment,
  type ReviewRecord,
} from '@/services/api'

const STATUSES: ChecklistStatus[] = ['pending', 'passed', 'failed', 'waived', 'not_applicable']

export function ReleaseEditorPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [reviews, setReviews] = useState<ReviewRecord[]>([])
  const [projectId, setProjectId] = useState('')
  const [reviewId, setReviewId] = useState('')
  const [report, setReport] = useState<ReleaseAssessment | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    listProjects()
      .then((items) => {
        if (!cancelled) {
          setProjects(items)
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'The repositories could not be read.')
        }
      })
    listReviews()
      .then((items) => {
        if (!cancelled) {
          setReviews(items)
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'The reviews could not be read.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!projectId || !reviewId) {
      setReport(null)
      return
    }
    let cancelled = false
    setBusy(true)
    previewRelease(projectId, reviewId)
      .then((next) => {
        if (!cancelled) {
          setReport(next)
          setError(null)
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setReport(null)
          setError(caught instanceof Error ? caught.message : 'The assessment could not be built.')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBusy(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [projectId, reviewId])

  const projectReviews = reviews.filter((item) => item.project_id === projectId)

  async function saveReport() {
    if (!projectId || !reviewId) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      const saved = await createReleaseReport(projectId, reviewId)
      navigate(`/releases/${saved.id}`)
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The report could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        phase="Phase 4"
        title="New release report"
        description="Choose a repository and a review run. Record a disposition for each finding and a status for each checklist item. This screen does not approve the release."
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <label className="text-sm" htmlFor="release-project">
          Repository
          <select
            id="release-project"
            className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
            value={projectId}
            onChange={(event) => {
              setProjectId(event.target.value)
              setReviewId('')
            }}
          >
            <option value="">Select a repository</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm" htmlFor="release-review">
          Review run
          <select
            id="release-review"
            className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
            value={reviewId}
            onChange={(event) => setReviewId(event.target.value)}
          >
            <option value="">Select a review</option>
            {projectReviews.map((review) => (
              <option key={review.id} value={review.id}>
                {review.status} · {review.model} · {review.created_at}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}
      {busy && <p className="mb-4 text-sm text-muted-foreground">Reading the local assessment…</p>}
      {report && (
        <>
          <ReleaseReportView report={report} />
          <div className="mt-8 space-y-6">
            <h2 className="font-serif text-2xl">Finding decisions</h2>
            <p className="text-sm text-muted-foreground">
              A critical waiver or dismissal needs a reason and a reviewer. A waiver stays in the waiver list.
            </p>
            {report.findings.length === 0 && <p className="text-sm">This review has no findings.</p>}
            {report.findings.map((finding) => (
              <FindingForm
                key={finding.id}
                reviewId={reviewId}
                finding={finding}
                onSaved={setReport}
                onError={setError}
              />
            ))}
            <h2 className="font-serif text-2xl">Checklist</h2>
            <p className="text-sm text-muted-foreground">
              Passed, waived, and not applicable each need a reason and a reviewer. Critical and high findings are
              decided individually.
            </p>
            {report.checklist.map((item) =>
              item.key === 'critical_high' ? (
                <p key={item.key} className="text-sm">
                  {item.label}: {item.evidence}
                </p>
              ) : (
                <ChecklistForm
                  key={item.key}
                  reviewId={reviewId}
                  item={item}
                  onSaved={setReport}
                  onError={setError}
                />
              ),
            )}
            <Button type="button" onClick={() => void saveReport()} disabled={busy}>
              Save release report
            </Button>
          </div>
        </>
      )}
      <p className="mt-6 text-sm">
        <Link to="/releases" className="underline">
          Back to release reports
        </Link>
      </p>
    </>
  )
}

function FindingForm({
  reviewId,
  finding,
  onSaved,
  onError,
}: {
  reviewId: string
  finding: FindingDisposition
  onSaved: (report: ReleaseAssessment) => void
  onError: (message: string) => void
}) {
  const [decision, setDecision] = useState(finding.decision || 'dismissed')
  const [reason, setReason] = useState(finding.reason)
  const [reviewer, setReviewer] = useState(finding.reviewer)

  async function save() {
    try {
      onSaved(await saveFindingDecision(reviewId, finding.id, decision, reason, reviewer))
    } catch (caught: unknown) {
      onError(caught instanceof Error ? caught.message : 'The decision could not be saved.')
    }
  }

  return (
    <form
      className="grid gap-3 rounded-lg border border-border p-4"
      onSubmit={(event) => {
        event.preventDefault()
        void save()
      }}
    >
      <p className="text-sm font-medium">
        {finding.severity}: {finding.title}
      </p>
      <label className="text-sm">
        Decision
        <select
          className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
          value={decision}
          onChange={(event) => setDecision(event.target.value)}
        >
          <option value="dismissed">Dismissed</option>
          <option value="confirmed">Confirmed</option>
          <option value="waived">Waived</option>
        </select>
      </label>
      <label className="text-sm">
        Reason
        <input
          className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      <label className="text-sm">
        Reviewer
        <input
          className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
          value={reviewer}
          onChange={(event) => setReviewer(event.target.value)}
        />
      </label>
      <Button type="submit" variant="outline">
        Save decision
      </Button>
    </form>
  )
}

function ChecklistForm({
  reviewId,
  item,
  onSaved,
  onError,
}: {
  reviewId: string
  item: ChecklistItem
  onSaved: (report: ReleaseAssessment) => void
  onError: (message: string) => void
}) {
  const [status, setStatus] = useState<ChecklistStatus>(item.status)
  const [reason, setReason] = useState(item.reason)
  const [reviewer, setReviewer] = useState(item.reviewer)

  async function save() {
    try {
      onSaved(await saveChecklistDecision(reviewId, item.key, status, reason, reviewer))
    } catch (caught: unknown) {
      onError(caught instanceof Error ? caught.message : 'The checklist item could not be saved.')
    }
  }

  return (
    <form
      className="grid gap-3 rounded-lg border border-border p-4"
      onSubmit={(event) => {
        event.preventDefault()
        void save()
      }}
    >
      <p className="text-sm font-medium">{item.label}</p>
      <label className="text-sm">
        Status
        <select
          className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
          value={status}
          onChange={(event) => setStatus(event.target.value as ChecklistStatus)}
        >
          {STATUSES.map((choice) => (
            <option key={choice} value={choice}>
              {choice}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm">
        Reason
        <input
          className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      <label className="text-sm">
        Reviewer
        <input
          className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
          value={reviewer}
          onChange={(event) => setReviewer(event.target.value)}
        />
      </label>
      <Button type="submit" variant="outline">
        Save checklist item
      </Button>
    </form>
  )
}
