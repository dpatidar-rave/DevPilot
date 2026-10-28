import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ConnectionError } from '@/components/ConnectionError'
import { DiffView } from '@/components/DiffView'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useLocalResource } from '@/hooks/useLocalResource'
import {
  readChanges,
  readFileDiff,
  readProject,
  saveSelection,
  type ChangeFile,
  type DiffScope,
  type FileDiff,
} from '@/services/api'

export function RepositoryPage() {
  const { projectId = '' } = useParams()
  const project = useLocalResource(useCallback(() => readProject(projectId), [projectId]))
  const [base, setBase] = useState<string | undefined>(undefined)
  const changes = useLocalResource(useCallback(() => readChanges(projectId, base), [projectId, base]))
  const [selected, setSelected] = useState<string[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [active, setActive] = useState<{ scope: DiffScope; path: string } | null>(null)
  const [diff, setDiff] = useState<FileDiff | null>(null)
  const [diffError, setDiffError] = useState<string | null>(null)

  useEffect(() => {
    if (changes.state.status === 'ready') {
      setSelected(changes.state.data.selected_paths)
    }
  }, [changes.state])

  async function openDiff(scope: DiffScope, path: string) {
    setActive({ scope, path })
    setDiff(null)
    setDiffError(null)
    const comparison = changes.state.status === 'ready' ? changes.state.data.base : base
    try {
      setDiff(await readFileDiff(projectId, scope, path, comparison))
    } catch (caught) {
      setDiffError(caught instanceof Error ? caught.message : 'The diff could not be read.')
    }
  }

  async function onSave() {
    if (changes.state.status !== 'ready') {
      return
    }
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const paths = await saveSelection(projectId, selected, changes.state.data.base)
      setSelected(paths)
      setMessage('Saved on this machine for a later review. This build does not start a review.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The selection was not saved.')
    } finally {
      setSaving(false)
    }
  }

  function toggle(path: string) {
    setSelected((current) =>
      current.includes(path) ? current.filter((item) => item !== path) : [...current, path],
    )
  }

  return (
    <>
      <PageHeader
        phase="Phase 1"
        title={project.state.status === 'ready' ? project.state.data.name : 'Repository'}
        description="Working tree, branches, and diffs stay on this machine. Nothing here commits or switches branches."
      />
      {project.state.status === 'loading' && <p>Reading the local repository…</p>}
      {project.state.status === 'error' && (
        <ConnectionError message={project.state.message} onRetry={project.reload} />
      )}
      {project.state.status === 'ready' && (
        <section className="space-y-3 rounded-lg border border-border bg-card px-5 py-4">
          <p className="break-all font-mono text-xs text-muted-foreground">{project.state.data.path}</p>
          <div className="flex flex-wrap gap-2">
            <Badge>{project.state.data.detached ? 'Detached HEAD' : project.state.data.branch ?? 'No branch'}</Badge>
            {project.state.data.dirty && <Badge>Uncommitted changes</Badge>}
            {project.state.data.magento.detected && (
              <Badge>{project.state.data.magento.edition ?? 'Magento'}</Badge>
            )}
          </div>
          {project.state.data.head_sha && (
            <p className="text-sm">
              <span className="font-mono">{project.state.data.head_sha}</span>
              {project.state.data.head_subject ? ` ${project.state.data.head_subject}` : ''}
            </p>
          )}
          <MagentoFacts detected={project.state.data.magento.detected} edition={project.state.data.magento.edition} magentoVersion={project.state.data.magento.magento_version} phpVersion={project.state.data.magento.php_version} />
          {project.state.data.uncommitted_warning && (
            <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm">
              {project.state.data.uncommitted_warning}
            </p>
          )}
        </section>
      )}

      {changes.state.status === 'error' && (
        <div className="mt-6">
          <ConnectionError message={changes.state.message} onRetry={changes.reload} />
        </div>
      )}
      {changes.state.status === 'ready' && (
        <div className="mt-8 space-y-6">
          <label className="block max-w-xs text-sm" htmlFor="base-branch">
            Compare with
            <select
              id="base-branch"
              className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2"
              value={base ?? changes.state.data.base ?? ''}
              onChange={(event) => setBase(event.target.value)}
            >
              {changes.state.data.branches.map((branch) => (
                <option key={branch} value={branch}>
                  {branch}
                </option>
              ))}
            </select>
          </label>
          {changes.state.data.truncated && (
            <p className="text-sm text-muted-foreground">The change list was shortened.</p>
          )}
          <ChangeGroup title="Staged changes" scope="staged" files={changes.state.data.staged} selected={selected} active={active} onToggle={toggle} onOpen={(path) => void openDiff('staged', path)} />
          <ChangeGroup title="Unstaged changes" scope="unstaged" files={changes.state.data.unstaged} selected={selected} active={active} onToggle={toggle} onOpen={(path) => void openDiff('unstaged', path)} />
          <ChangeGroup title="Committed differences" scope="committed" files={changes.state.data.committed} selected={selected} active={active} onToggle={toggle} onOpen={(path) => void openDiff('committed', path)} />
          <ChangeGroup title="Untracked files" scope="untracked" files={changes.state.data.untracked} selected={selected} active={active} onToggle={toggle} onOpen={(path) => void openDiff('untracked', path)} />
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" onClick={() => void onSave()} disabled={saving}>
              {saving ? 'Saving…' : 'Save review selection'}
            </Button>
            <p className="text-sm text-muted-foreground">
              Selected files are stored locally. A review sends only those files to the local model.
            </p>
            <Link
              className="text-sm text-primary"
              to={`/reviews/new?project=${projectId}&base=${encodeURIComponent(changes.state.data.base ?? '')}`}
            >
              Review the saved selection
            </Link>
          </div>
          {message && <p role="status" className="text-sm">{message}</p>}
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          {diffError && <p role="alert" className="text-sm text-destructive">{diffError}</p>}
          {diff && (
            <section>
              <h2 className="mb-3 font-mono text-sm">{diff.path}</h2>
              <DiffView
                lines={diff.lines}
                language={diff.language}
                binary={diff.binary}
                truncated={diff.truncated}
                skipped={diff.skipped}
              />
            </section>
          )}
        </div>
      )}
    </>
  )
}

function MagentoFacts({
  detected,
  edition,
  magentoVersion,
  phpVersion,
}: {
  detected: boolean
  edition: string | null
  magentoVersion: string | null
  phpVersion: string | null
}) {
  if (!detected) {
    return (
      <p className="text-sm text-muted-foreground">
        Magento was not detected from composer.json and app/etc/di.xml.
      </p>
    )
  }
  return (
    <div className="text-sm">
      <p>{edition ?? 'Magento project'}</p>
      <p>{magentoVersion ? `Magento ${magentoVersion}` : 'Magento version was not established.'}</p>
      <p>{phpVersion ? `PHP ${phpVersion}` : 'PHP version was not established.'}</p>
    </div>
  )
}

function ChangeGroup({
  title,
  scope,
  files,
  selected,
  active,
  onToggle,
  onOpen,
}: {
  title: string
  scope: DiffScope
  files: ChangeFile[]
  selected: string[]
  active: { scope: DiffScope; path: string } | null
  onToggle: (path: string) => void
  onOpen: (path: string) => void
}) {
  return (
    <section>
      <h2 className="font-serif text-2xl">{title}</h2>
      {files.length === 0 && <p className="mt-2 text-sm text-muted-foreground">None.</p>}
      <ul className="mt-2 divide-y divide-border">
        {files.map((file, index) => {
          const id = `${scope}-${index}`
          return (
            <li key={id} className="flex items-start gap-3 py-2">
              <input
                id={id}
                type="checkbox"
                className="mt-1"
                checked={selected.includes(file.path)}
                disabled={file.skipped !== null}
                onChange={() => onToggle(file.path)}
              />
              <div className="min-w-0">
                <button
                  type="button"
                  className={`block break-all text-left font-mono text-xs ${active?.path === file.path && active.scope === scope ? 'text-primary' : ''}`}
                  onClick={() => onOpen(file.path)}
                >
                  <span className="mr-2 text-muted-foreground">{file.status}</span>
                  {file.path}
                </button>
                {file.skipped === 'sensitive' && (
                  <p className="text-xs text-muted-foreground">Not loaded. It may contain credentials.</p>
                )}
                {file.skipped === 'generated' && (
                  <p className="text-xs text-muted-foreground">Not loaded. Generated directory.</p>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
