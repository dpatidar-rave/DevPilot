import type { HealthResponse } from '@/services/api'

export function ModelStatus({ health }: { health: HealthResponse }) {
  const rows = [
    ['Provider', 'Ollama, on this machine'],
    ['Model', health.ai.model],
    ['Context length', String(health.ai.context_length)],
    ['Temperature', String(health.ai.temperature)],
    ['Maximum output', `${health.ai.max_output_tokens} tokens`],
    ['Timeout', `${health.ai.timeout_seconds} seconds`],
    ['Keep-alive', health.ai.keep_alive],
    ['Concurrent requests', String(health.ai.max_concurrent_requests)],
    ['Endpoint', health.ai.endpoint],
    ['Availability', 'Not checked'],
  ]

  return (
    <section aria-label="Local model" className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-5 py-4">
        <h2 className="font-serif text-2xl">Local model</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          DevPilot does not contact Ollama until you start a review. A missing model is not
          downloaded automatically. Run <code className="font-mono text-xs">ollama pull {health.ai.model}</code>{' '}
          yourself before a later review phase.
        </p>
      </div>
      <dl className="grid gap-px bg-border sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="bg-card px-5 py-3">
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
            <dd className="mt-1 font-mono text-sm">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
