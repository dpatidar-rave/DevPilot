/** Client-side checks. The backend remains the authority. */

const CLOUD_MODEL_PATTERN =
  /(?:^|[^a-z0-9])(?:gpt-|chatgpt|claude|gemini|text-davinci|text-embedding-|dall-e|openai|anthropic|openrouter|bedrock|vertex-ai|azure-openai)|(?:^|[^a-z0-9])o[13](?:$|[^a-z0-9])/i
const MODEL_NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/
const PARAMETER_PATTERN = /(?:^|[^0-9])(\d+)b(?:$|[^a-z0-9])/gi

export const DEFAULT_MODEL = 'qwen2.5-coder:7b'
export const LARGE_MODEL_THRESHOLD = 20

export function isLoopbackHost(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, '').replace(/\.+$/g, '')
  if (host === 'localhost' || host === '::1') {
    return true
  }
  const parts = host.split('.')
  if (parts.length !== 4 || parts[0] !== '127') {
    return false
  }
  return parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255)
}

export function largestParameterSize(model: string): number {
  let largest = 0
  for (const match of model.matchAll(PARAMETER_PATTERN)) {
    const size = Number(match[1])
    if (!Number.isNaN(size)) {
      largest = Math.max(largest, size)
    }
  }
  return largest
}

export function modelError(model: string, largeConfirmed: boolean): string | null {
  const name = model.trim()
  if (!MODEL_NAME_PATTERN.test(name)) {
    return 'Model name must be a local Ollama tag made of letters, numbers, and . _ : / -.'
  }
  if (CLOUD_MODEL_PATTERN.test(name)) {
    return `Hosted model names are not allowed. The local default is ${DEFAULT_MODEL}.`
  }
  const size = largestParameterSize(name)
  if (size >= LARGE_MODEL_THRESHOLD && !largeConfirmed) {
    return (
      `${name} is ${size}B parameters. On a 16 GB Mac the default is ${DEFAULT_MODEL}. ` +
      `Models at ${LARGE_MODEL_THRESHOLD}B or larger are an optional experiment. ` +
      'Confirm the extra memory use before selecting one.'
    )
  }
  return null
}

export function endpointError(value: string): string | null {
  let url: URL
  try {
    url = new URL(value.trim())
  } catch {
    return 'Enter an Ollama origin on this machine, such as http://127.0.0.1:11434.'
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return 'Ollama endpoint must use http or https.'
  }
  if (url.username || url.password || url.search || url.hash) {
    return 'Ollama endpoint cannot include credentials, a query, or a fragment.'
  }
  if (url.pathname !== '/' && url.pathname !== '') {
    return 'Ollama endpoint must not include a path.'
  }
  if (!url.port) {
    return 'Ollama endpoint must include an explicit port.'
  }
  if (!isLoopbackHost(url.hostname)) {
    return 'Ollama endpoint must be a loopback address. Remote inference endpoints are not allowed.'
  }
  return null
}

export interface SettingsDraft {
  model: string
  contextLength: string
  temperature: string
  maxOutputTokens: string
  timeoutSeconds: string
  ollamaEndpoint: string
  largeModelConfirmed: boolean
}

export interface SettingsPayload {
  model: string
  context_length: number
  temperature: number
  max_output_tokens: number
  timeout_seconds: number
  ollama_endpoint: string
  large_model_confirmed: boolean
}

export function settingsPayload(
  draft: SettingsDraft,
): { ok: true; body: SettingsPayload } | { ok: false; message: string } {
  const endpoint = endpointError(draft.ollamaEndpoint)
  if (endpoint) {
    return { ok: false, message: endpoint }
  }
  const model = modelError(draft.model, draft.largeModelConfirmed)
  if (model) {
    return { ok: false, message: model }
  }
  const contextLength = Number(draft.contextLength)
  const temperature = Number(draft.temperature)
  const maxOutputTokens = Number(draft.maxOutputTokens)
  const timeoutSeconds = Number(draft.timeoutSeconds)
  if (!Number.isInteger(contextLength) || contextLength < 1024 || contextLength > 32768) {
    return { ok: false, message: 'Context length must be an integer from 1024 to 32768.' }
  }
  if (Number.isNaN(temperature) || temperature < 0 || temperature > 1) {
    return { ok: false, message: 'Temperature must be between 0 and 1.' }
  }
  if (!Number.isInteger(maxOutputTokens) || maxOutputTokens < 128 || maxOutputTokens > 4096) {
    return { ok: false, message: 'Maximum output must be an integer from 128 to 4096.' }
  }
  if (Number.isNaN(timeoutSeconds) || timeoutSeconds < 10 || timeoutSeconds > 600) {
    return { ok: false, message: 'Timeout must be between 10 and 600 seconds.' }
  }
  return {
    ok: true,
    body: {
      model: draft.model.trim(),
      context_length: contextLength,
      temperature,
      max_output_tokens: maxOutputTokens,
      timeout_seconds: timeoutSeconds,
      ollama_endpoint: draft.ollamaEndpoint.trim(),
      large_model_confirmed: largestParameterSize(draft.model) >= LARGE_MODEL_THRESHOLD
        ? draft.largeModelConfirmed
        : false,
    },
  }
}
