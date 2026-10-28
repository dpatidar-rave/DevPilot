import { FormEvent, useCallback, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ConnectionError } from '@/components/ConnectionError'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { useLocalResource } from '@/hooks/useLocalResource'
import { listProjects, readChanges, readSettings, startReview } from '@/services/api'

export function ReviewSetupPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const requestedProject = params.get('project') ?? ''
  const requestedBase = params.get('base') ?? undefined
  const projects = useLocalResource(useCallback(() => listProjects(), []))
  const settings = useLocalResource(useCallback(() => readSettings(), []))
  const [projectId, setProjectId] = useState(requestedProject)
  const [base, setBase] = useState(requestedBase ?? '')
  const changes = useLocalResource(
    useCallback(() => {
      if (projectId === '') {
        return Promise.resolve(null)
      }
      return readChanges(projectId, base || undefined)
    }, [projectId, base]),
  )
  const [selected, setSelected] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const visible = visibleFiles(
    changes.state.status === 'ready' ? changes.state.data : null,
  )
  const chosen = selected ?? (changes.state.status === 'ready' && changes.state.data
    ? changes.state.data.selected_paths
    : [])

  function visibleFiles(
  data: {
    staged: { path: string; skipped: string | null }[]
    unstaged: { path: string; skipped: string | null }[]
    committed: { path: string; skipped: string | null }[]
    untracked: { path: string; skipped: string | null }[]
  } | null,
) {
  if (data === null) {
    return []
  }
  const seen = new Set<string>()
  const files: { path: string }[] = []
  for (const file of [...data.staged, ...data.unstaged, ...data.committed, ...data.untracked]) {
    if (file.skipped !== null || seen.has(file.path)) {
      continue
    }
    seen.add(file.path)
    files.push({ path: file.path })
  }
  return files
}

function toggle(path: string) {
    setSelected(chosen.includes(path) ? chosen.filter((item) => item !== path) : [...chosen, path])
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (changes.state.status !== 'ready' || changes.state.data === null) {
      return
    }
    setSaving(true)
    setError(null)
    try {
      const review = await startReview(projectId, changes.state.data.base ?? base, chosen)
      navigate(`/reviews/${review.id}`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The review did not start.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        phase="Phase 2"
        title="Start a review"
        description="Choose a repository, a base branch, and the files to send. DevPilot uses only the configured local Ollama model."
      />
      <p className="mb-6 max-w-2xl text-sm leading-6">
        Findings will be AI suggestions. They are not deterministic test results, and they are not
        guaranteed to be correct. The model cannot change the repository or run tools.
      </p>
      {settings.state.status === 'ready' && (
        <p className="mb-6 text-sm">
          Model <span className="font-mono">{settings.state.data.model}</span>
          {' · '}
          context {settings.state.data.context_length}
          {' · '}
          temperature {settings.state.data.temperature}
          {' · '}
          {settings.state.data.ollama_endpoint}
        </p>
      )}
      {projects.state.status === 'error' && (
        <ConnectionError message={projects.state.message} onRetry={projects.reload} />
      )}
      <form onSubmit={(event) => void onSubmit(event)} className="space-y-6">
        <label className="block max-w-md text-sm" htmlFor="review-project">
          Repository
          <select
            id="review-project"
            className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
            value={projectId}
            onChange={(event) => {
              setProjectId(event.target.value)
              setSelected(null)
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
        {changes.state.status === 'error' && (
          <ConnectionError message={changes.state.message} onRetry={changes.reload} />
        )}
        {changes.state.status === 'ready' && changes.state.data && (
          <>
            <label className="block max-w-xs text-sm" htmlFor="review-base">
              Base branch
              <select
                id="review-base"
                className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
                value={base || changes.state.data.base || ''}
                onChange={(event) => {
                  setBase(event.target.value)
                  setSelected(null)
                }}
              >
                {changes.state.data.branches.map((branch) => (
                  <option key={branch} value={branch}>
                    {branch}
                  </option>
                ))}
              </select>
            </label>
            <fieldset>
              <legend className="text-sm">Files in this review</legend>
              {visible.length === 0 && (
                <p className="mt-2 text-sm text-muted-foreground">
                  There are no reviewable text changes against this base.
                </p>
              )}
              <ul className="mt-2 divide-y divide-border">
                {visible.map((file) => (
                  <li key={file.path} className="flex items-center gap-3 py-2">
                    <input
                      type="checkbox"
                      checked={chosen.includes(file.path)}
                      onChange={() => toggle(file.path)}
                    />
                    <span className="font-mono text-xs">{file.path}</span>
                  </li>
                ))}
              </ul>
            </fieldset>
            <Button type="submit" disabled={saving || chosen.length === 0}>
              {saving ? 'Starting…' : 'Start local review'}
            </Button>
          </>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </form>
    </>
  )
}
