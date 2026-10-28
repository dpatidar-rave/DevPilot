import { useEffect, useState } from 'react'

import { ConnectionError } from '@/components/ConnectionError'
import { PageHeader } from '@/components/PageHeader'
import { QualityResultList } from '@/components/QualityResultList'
import { Button } from '@/components/ui/button'
import { useLocalResource } from '@/hooks/useLocalResource'
import {
  listProjects,
  listQualityChecks,
  listReviews,
  readQualityCatalog,
  runQualityCheck,
  saveQualityCommand,
  type QualityCatalog,
  type QualityCheckRecord,
  type ReviewRecord,
} from '@/services/api'

const WARNING =
  'Approved project scripts can still have side effects. PHPUnit and the Magento CLI can write files or bootstrap the application. DevPilot does not install Composer packages, change project configuration, or run deployment commands, and it runs a command only after you confirm it.'

export function QualityPage() {
  const projects = useLocalResource(listProjects)
  const [projectId, setProjectId] = useState('')
  const [catalog, setCatalog] = useState<QualityCatalog | null>(null)
  const [runs, setRuns] = useState<QualityCheckRecord[]>([])
  const [reviews, setReviews] = useState<ReviewRecord[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({})
  const [reviewId, setReviewId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    if (!projectId) {
      setCatalog(null)
      setRuns([])
      setReviews([])
      return
    }
    let cancelled = false
    setError(null)
    void Promise.all([
      readQualityCatalog(projectId),
      listQualityChecks(projectId),
      listReviews(),
    ])
      .then(([nextCatalog, nextRuns, nextReviews]) => {
        if (cancelled) {
          return
        }
        setCatalog(nextCatalog)
        setRuns(nextRuns)
        setReviews(nextReviews.filter((review) => review.project_id === projectId))
        const nextDrafts: Record<string, string> = {}
        for (const tool of nextCatalog.tools) {
          const argv = tool.saved_argv.length > 0 ? tool.saved_argv : tool.suggested_argv
          nextDrafts[tool.tool] = argv.join('\n')
        }
        setDrafts(nextDrafts)
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'The quality checks could not be read.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [projectId, reloadKey])

  async function onSave(tool: string) {
    const argv = (drafts[tool] ?? '')
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line !== '')
    setBusy(true)
    setError(null)
    try {
      await saveQualityCommand(projectId, tool, argv)
      setConfirmed((current) => ({ ...current, [tool]: false }))
      setReloadKey((value) => value + 1)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The command could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  async function onRun(tool: string) {
    if (!confirmed[tool]) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      await runQualityCheck(projectId, tool, true, reviewId || null)
      setConfirmed((current) => ({ ...current, [tool]: false }))
      setReloadKey((value) => value + 1)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The command could not be run.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        phase="Phase 3"
        title="Quality checks"
        description="Deterministic command results for one registered repository. These are not AI suggestions. A command runs only after you save it and confirm that run."
      />
      <p className="mb-6 max-w-3xl rounded-lg border border-border bg-card px-5 py-4 text-sm leading-6">
        {WARNING}
      </p>
      {projects.state.status === 'error' && (
        <ConnectionError message={projects.state.message} onRetry={projects.reload} />
      )}
      <label className="block max-w-md text-sm" htmlFor="quality-project">
        Repository
        <select
          id="quality-project"
          className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
          value={projectId}
          onChange={(event) => {
            setProjectId(event.target.value)
            setCatalog(null)
            setDrafts({})
            setConfirmed({})
            setReviewId('')
          }}
        >
          <option value="">Choose a repository</option>
          {projects.state.status === 'ready' &&
            projects.state.data.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
        </select>
      </label>
      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
      {catalog && (
        <div className="mt-6 space-y-6">
          <p className="text-sm">
            <span className="text-muted-foreground">Working directory. </span>
            <span className="font-mono">{catalog.working_directory}</span>
          </p>
          <label className="block max-w-md text-sm" htmlFor="quality-review">
            Attach to a review run
            <select
              id="quality-review"
              className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
              value={reviewId}
              onChange={(event) => setReviewId(event.target.value)}
            >
              <option value="">Do not attach</option>
              {reviews.map((review) => (
                <option key={review.id} value={review.id}>
                  {review.created_at} · {review.status}
                </option>
              ))}
            </select>
          </label>
          {catalog.tools.map((tool) => {
            const savedText = tool.saved_argv.join('\n')
            const draft = drafts[tool.tool] ?? ''
            const dirty = draft.trim() !== savedText
            return (
              <section key={tool.tool} className="rounded-lg border border-border bg-card px-5 py-4">
                <h2 className="font-serif text-2xl">{tool.label}</h2>
                <p className="mt-2 text-sm">
                  {tool.available ? 'Tool files were found.' : tool.reason || 'This check is not available.'}
                </p>
                {tool.files.length > 0 && (
                  <p className="mt-1 font-mono text-xs text-muted-foreground">{tool.files.join(', ')}</p>
                )}
                <label className="mt-4 block text-sm" htmlFor={`argv-${tool.tool}`}>
                  Arguments, one per line
                  <textarea
                    id={`argv-${tool.tool}`}
                    className="mt-1 min-h-28 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                    value={draft}
                    onChange={(event) =>
                      setDrafts((current) => ({ ...current, [tool.tool]: event.target.value }))
                    }
                  />
                </label>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <Button type="button" variant="outline" disabled={busy} onClick={() => void onSave(tool.tool)}>
                    Save command
                  </Button>
                  <label className="flex items-center gap-2 text-sm" htmlFor={`confirm-${tool.tool}`}>
                    <input
                      id={`confirm-${tool.tool}`}
                      type="checkbox"
                      checked={confirmed[tool.tool] === true}
                      onChange={(event) =>
                        setConfirmed((current) => ({ ...current, [tool.tool]: event.target.checked }))
                      }
                    />
                    I confirm this run
                  </label>
                  <Button
                    type="button"
                    disabled={busy || !confirmed[tool.tool] || tool.saved_argv.length === 0 || dirty}
                    onClick={() => void onRun(tool.tool)}
                  >
                    Run saved command
                  </Button>
                </div>
              </section>
            )
          })}
          <section>
            <h2 className="font-serif text-2xl">Results</h2>
            <p className="mb-4 mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Each row is the exit result of a command you confirmed. It is not an AI suggestion.
            </p>
            <QualityResultList runs={runs} />
          </section>
        </div>
      )}
    </>
  )
}
