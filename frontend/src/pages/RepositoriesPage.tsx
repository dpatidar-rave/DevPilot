import { FormEvent, useCallback, useState } from 'react'
import { Link } from 'react-router-dom'

import { ConnectionError } from '@/components/ConnectionError'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useLocalResource } from '@/hooks/useLocalResource'
import { browseDirectories, listProjects, registerProject } from '@/services/api'

export function RepositoriesPage() {
  const projects = useLocalResource(useCallback(() => listProjects(), []))
  const [browserPath, setBrowserPath] = useState<string | undefined>(undefined)
  const browser = useLocalResource(useCallback(() => browseDirectories(browserPath), [browserPath]))
  const [path, setPath] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function register(target: string) {
    setSaving(true)
    setError(null)
    try {
      await registerProject(target, name)
      setPath('')
      setName('')
      projects.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The repository was not registered.')
    } finally {
      setSaving(false)
    }
  }

  function FolderBrowser({
  path: folder,
  parent,
  directories,
  truncated,
  saving,
  onOpen,
  onRegister,
}: {
  path: string
  parent: string | null
  directories: string[]
  truncated: boolean
  saving: boolean
  onOpen: (path: string) => void
  onRegister: (path: string) => void
}) {
  return (
    <div className="mt-3 space-y-3">
      <p className="break-all font-mono text-xs text-muted-foreground">{folder}</p>
      <div className="flex flex-wrap gap-2">
        {parent && (
          <Button type="button" variant="outline" size="sm" onClick={() => onOpen(parent)}>
            Parent folder
          </Button>
        )}
        <Button type="button" size="sm" disabled={saving} onClick={() => onRegister(folder)}>
          Register this folder
        </Button>
      </div>
      <ul className="divide-y divide-border">
        {directories.map((directory) => (
          <li key={directory}>
            <button
              type="button"
              className="w-full py-2 text-left text-sm hover:text-primary"
              onClick={() => onOpen(folder === '/' ? `/${directory}` : `${folder}/${directory}`)}
            >
              {directory}
            </button>
          </li>
        ))}
      </ul>
      {truncated && <p className="text-xs text-muted-foreground">The folder list was shortened.</p>}
    </div>
  )
}

function onSubmit(event: FormEvent) {
    event.preventDefault()
    void register(path.trim())
  }

  return (
    <>
      <PageHeader
        phase="Phase 1"
        title="Repositories"
        description="Register a local Git working tree. DevPilot reads it and does not commit, switch branches, or change files."
      />
      <form onSubmit={onSubmit} className="max-w-xl space-y-4">
        <label className="block text-sm" htmlFor="repo-path">
          Absolute path
          <input
            id="repo-path"
            value={path}
            onChange={(event) => setPath(event.target.value)}
            placeholder="/Users/you/sites/shop"
            className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2 font-mono text-sm"
            required
          />
        </label>
        <label className="block text-sm" htmlFor="repo-name">
          Display name
          <input
            id="repo-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Optional. Defaults to the folder name."
            className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
          />
        </label>
        <Button type="submit" disabled={saving}>
          {saving ? 'Checking…' : 'Register path'}
        </Button>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </form>

      <section className="mt-8 rounded-lg border border-border bg-card px-5 py-4">
        <h2 className="font-serif text-2xl">Choose a folder</h2>
        {browser.state.status === 'loading' && <p className="mt-3 text-sm">Reading local folders…</p>}
        {browser.state.status === 'error' && (
          <div className="mt-3">
            <ConnectionError message={browser.state.message} onRetry={browser.reload} />
          </div>
        )}
        {browser.state.status === 'ready' && (
          <FolderBrowser
            path={browser.state.data.path}
            parent={browser.state.data.parent}
            directories={browser.state.data.directories}
            truncated={browser.state.data.truncated}
            saving={saving}
            onOpen={setBrowserPath}
            onRegister={(folder) => {
              setPath(folder)
              void register(folder)
            }}
          />
        )}
      </section>

      <section className="mt-8">
        <h2 className="font-serif text-2xl">Registered</h2>
        {projects.state.status === 'error' && (
          <div className="mt-3">
            <ConnectionError message={projects.state.message} onRetry={projects.reload} />
          </div>
        )}
        {projects.state.status === 'ready' && projects.state.data.length === 0 && (
          <p className="mt-3 text-sm text-muted-foreground">No repositories are registered in the local database.</p>
        )}
        {projects.state.status === 'ready' && projects.state.data.length > 0 && (
          <ul className="mt-4 divide-y divide-border">
            {projects.state.data.map((project) => (
              <li key={project.id} className="flex items-start justify-between gap-4 py-3">
                <div>
                  <Link to={`/repositories/${project.id}`} className="font-medium hover:text-primary">
                    {project.name}
                  </Link>
                  <p className="font-mono text-xs text-muted-foreground">{project.path}</p>
                  {project.inspection_error && (
                    <p className="mt-1 text-sm text-destructive">{project.inspection_error}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  {project.magento && <Badge>Magento</Badge>}
                  {project.detached && <Badge>Detached HEAD</Badge>}
                  {project.branch && <Badge>{project.branch}</Badge>}
                  {project.dirty && <Badge>Uncommitted</Badge>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
