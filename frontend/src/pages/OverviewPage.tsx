import { ConnectionError } from '@/components/ConnectionError'
import { ModelStatus } from '@/components/ModelStatus'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { useLocalResource } from '@/hooks/useLocalResource'
import { checkHealth, listProjects } from '@/services/api'

export function OverviewPage() {
  const health = useLocalResource(checkHealth)
  const projects = useLocalResource(listProjects)

  return (
    <>
      <PageHeader
        title="Overview"
        description="Local status for this machine. Review execution is not part of this build, and DevPilot does not invent findings."
      />
      {health.state.status === 'loading' && <p>Checking the local backend…</p>}
      {health.state.status === 'error' && (
        <ConnectionError message={health.state.message} onRetry={health.reload} />
      )}
      {health.state.status === 'ready' && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatusCard label="Backend" value="Connected" detail={`DevPilot ${health.state.data.version}`} />
            <StatusCard
              label="Database"
              value={health.state.data.database === 'ok' ? 'SQLite ready' : 'SQLite unavailable'}
              detail={health.state.data.database_message ?? 'Stored only on this machine'}
            />
            <StatusCard
              label="Bind address"
              value={health.state.data.bind_host}
              detail="Loopback only"
            />
          </div>
          <ModelStatus health={health.state.data} />
          <section className="rounded-lg border border-border bg-card px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-serif text-2xl">Repositories</h2>
              <Badge>
                {projects.state.status === 'ready'
                  ? `${projects.state.data.length} stored`
                  : 'Checking'}
              </Badge>
            </div>
            {projects.state.status === 'error' && (
              <p className="mt-3 text-sm text-destructive">{projects.state.message}</p>
            )}
            {projects.state.status === 'ready' && projects.state.data.length === 0 && (
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                No repositories are registered in the local database.
              </p>
            )}
            {projects.state.status === 'ready' && projects.state.data.length > 0 && (
              <ul className="mt-4 divide-y divide-border">
                {projects.state.data.map((project) => (
                  <li key={project.id} className="py-3">
                    <p className="font-medium">{project.name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{project.path}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </>
  )
}

function StatusCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <section className="rounded-lg border border-border bg-card px-4 py-4">
      <h2 className="text-xs uppercase tracking-wide text-muted-foreground">{label}</h2>
      <p className="mt-2 font-medium" role="status">
        {value}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </section>
  )
}
