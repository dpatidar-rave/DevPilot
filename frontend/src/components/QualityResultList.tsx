import type { QualityCheckRecord } from '@/services/api'

export function QualityResultList({ runs }: { runs: QualityCheckRecord[] }) {
  if (runs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No deterministic command results are stored here. DevPilot does not invent sample results.
      </p>
    )
  }
  return (
    <ul className="space-y-4">
      {runs.map((run) => (
        <li key={run.id} className="rounded-lg border border-border bg-card px-5 py-4 text-sm">
          <p className="font-medium">
            {resultLabel(run.result)} · deterministic command result
          </p>
          <p className="mt-2">
            <span className="text-muted-foreground">Command. </span>
            <span className="font-mono">{run.command || 'Not recorded'}</span>
          </p>
          <p className="mt-1">
            <span className="text-muted-foreground">Working directory. </span>
            <span className="font-mono">{run.working_directory || 'Not recorded'}</span>
          </p>
          <p className="mt-1">
            <span className="text-muted-foreground">Started. </span>
            {run.started_at || 'Not recorded'}
          </p>
          <p className="mt-1">
            <span className="text-muted-foreground">Duration. </span>
            {run.duration_ms === null ? 'Not recorded' : `${run.duration_ms} ms`}
          </p>
          <p className="mt-1">
            <span className="text-muted-foreground">Exit status. </span>
            {run.exit_code === null ? 'none' : run.exit_code}
          </p>
          {run.note && <p className="mt-1 text-muted-foreground">{run.note}</p>}
          {run.output_truncated && (
            <p className="mt-1">Output was shortened because it exceeded the local limit.</p>
          )}
          <details className="mt-3">
            <summary>Standard output</summary>
            <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-xs">
              {run.stdout || 'No output.'}
            </pre>
          </details>
          <details className="mt-2">
            <summary>Error output</summary>
            <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-xs">
              {run.stderr || 'No output.'}
            </pre>
          </details>
        </li>
      ))}
    </ul>
  )
}

function resultLabel(result: QualityCheckRecord['result']): string {
  if (result === 'timed_out') {
    return 'Timed out'
  }
  if (result === 'pass') {
    return 'Pass'
  }
  if (result === 'fail') {
    return 'Fail'
  }
  if (result === 'skipped') {
    return 'Skipped'
  }
  return 'Stored'
}
