import { Button } from '@/components/ui/button'

export function ConnectionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  const offline = message.startsWith('Cannot reach')
  return (
    <div role="alert" className="rounded-lg border border-destructive/30 bg-card px-6 py-6">
      <h2 className="font-serif text-2xl">
        {offline ? 'Cannot reach the local backend' : 'DevPilot could not complete that request'}
      </h2>
      <p className="mt-3 max-w-2xl text-sm leading-6">{message}</p>
      {offline && (
        <>
          <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm leading-6">
            <li>
              Run <code className="font-mono text-xs">scripts/setup.sh</code> if dependencies are not
              installed.
            </li>
            <li>
              Run <code className="font-mono text-xs">scripts/start.sh</code> and wait until the health
              check succeeds.
            </li>
            <li>
              Open <code className="font-mono text-xs">http://127.0.0.1:5173</code> and retry.
            </li>
          </ol>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
            If Ollama is stopped or the selected model is missing, fix that on this machine. DevPilot
            does not download models and will not switch to a hosted provider.
          </p>
        </>
      )}
      <Button className="mt-5" type="button" onClick={onRetry}>
        Retry
      </Button>
    </div>
  )
}
