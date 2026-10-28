import { FormEvent, useEffect, useState } from 'react'

import { ConnectionError } from '@/components/ConnectionError'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { useLocalResource } from '@/hooks/useLocalResource'
import { ApiError, readSettings, updateSettings } from '@/services/api'
import { largestParameterSize, settingsPayload, type SettingsDraft } from '@/services/modelPolicy'

export function SettingsPage() {
  const resource = useLocalResource(readSettings)
  const [draft, setDraft] = useState<SettingsDraft | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (resource.state.status !== 'ready') {
      return
    }
    const settings = resource.state.data
    setDraft({
      model: settings.model,
      contextLength: String(settings.context_length),
      temperature: String(settings.temperature),
      maxOutputTokens: String(settings.max_output_tokens),
      timeoutSeconds: String(settings.timeout_seconds),
      ollamaEndpoint: settings.ollama_endpoint,
      largeModelConfirmed: settings.large_model_confirmed,
    })
  }, [resource.state])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!draft) {
      return
    }
    const parsed = settingsPayload(draft)
    if (!parsed.ok) {
      setError(parsed.message)
      setMessage(null)
      return
    }
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const saved = await updateSettings(parsed.body)
      setMessage('Saved in the local database on this machine.')
      setDraft({
        model: saved.model,
        contextLength: String(saved.context_length),
        temperature: String(saved.temperature),
        maxOutputTokens: String(saved.max_output_tokens),
        timeoutSeconds: String(saved.timeout_seconds),
        ollamaEndpoint: saved.ollama_endpoint,
        largeModelConfirmed: saved.large_model_confirmed,
      })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'The local settings were not saved.')
    } finally {
      setSaving(false)
    }
  }

  const large = draft ? largestParameterSize(draft.model) >= 20 : false

  return (
    <>
      <PageHeader
        title="Settings"
        description="Model name, context length, temperature, maximum output, timeout, and the Ollama endpoint. Changes stay in the local SQLite database."
      />
      {resource.state.status === 'loading' && <p>Reading local settings…</p>}
      {resource.state.status === 'error' && (
        <ConnectionError message={resource.state.message} onRetry={resource.reload} />
      )}
      {resource.state.status === 'ready' && draft && (
        <form onSubmit={onSubmit} className="max-w-xl space-y-5">
          <Field
            id="model"
            label="Model"
            value={draft.model}
            onChange={(model) => setDraft({ ...draft, model })}
            hint="Default for a 16 GB Mac: qwen2.5-coder:7b. Hosted model names are rejected."
          />
          {large && (
            <label className="flex items-start gap-3 text-sm leading-6" htmlFor="large-model">
              <input
                id="large-model"
                type="checkbox"
                className="mt-1"
                checked={draft.largeModelConfirmed}
                onChange={(event) =>
                  setDraft({ ...draft, largeModelConfirmed: event.target.checked })
                }
              />
              <span>
                I understand this model is 20B parameters or larger and can exhaust memory on a 16
                GB Mac. This is an optional experiment.
              </span>
            </label>
          )}
          <Field
            id="context-length"
            label="Context length"
            value={draft.contextLength}
            onChange={(contextLength) => setDraft({ ...draft, contextLength })}
            inputMode="numeric"
          />
          <Field
            id="temperature"
            label="Temperature"
            value={draft.temperature}
            onChange={(temperature) => setDraft({ ...draft, temperature })}
            inputMode="decimal"
          />
          <Field
            id="max-output"
            label="Maximum output tokens"
            value={draft.maxOutputTokens}
            onChange={(maxOutputTokens) => setDraft({ ...draft, maxOutputTokens })}
            inputMode="numeric"
          />
          <Field
            id="timeout"
            label="Timeout seconds"
            value={draft.timeoutSeconds}
            onChange={(timeoutSeconds) => setDraft({ ...draft, timeoutSeconds })}
            inputMode="decimal"
          />
          <Field
            id="endpoint"
            label="Ollama endpoint"
            value={draft.ollamaEndpoint}
            onChange={(ollamaEndpoint) => setDraft({ ...draft, ollamaEndpoint })}
            hint="Must resolve to a loopback address. The default is http://127.0.0.1:11434."
          />
          <p className="text-sm text-muted-foreground">
            Keep-alive is fixed at {resource.state.data.keep_alive}. Concurrent inference requests
            are fixed at {resource.state.data.max_concurrent_requests}. Availability is not checked
            until a review starts.
          </p>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
          <Button type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save on this machine'}
          </Button>
        </form>
      )}
    </>
  )
}

function Field({
  id,
  label,
  value,
  onChange,
  hint,
  inputMode,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  hint?: string
  inputMode?: 'numeric' | 'decimal' | 'text'
}) {
  return (
    <label htmlFor={id} className="block">
      <span className="text-sm font-medium">{label}</span>
      <input
        id={id}
        value={value}
        inputMode={inputMode ?? 'text'}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      {hint && <span className="mt-1 block text-xs leading-5 text-muted-foreground">{hint}</span>}
    </label>
  )
}
