import { endpointError, isLoopbackHost } from '@/services/modelPolicy'
import type { SettingsPayload } from '@/services/modelPolicy'

export class ApiError extends Error {
  readonly fieldErrors: { field: string; message: string }[]

  constructor(message: string, fieldErrors: { field: string; message: string }[] = []) {
    super(message)
    this.name = 'ApiError'
    this.fieldErrors = fieldErrors
  }
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  version: string
  database: 'ok' | 'error'
  database_message: string | null
  bind_host: string
  ai: {
    provider: 'ollama'
    endpoint: string
    model: string
    context_length: number
    temperature: number
    max_output_tokens: number
    timeout_seconds: number
    keep_alive: '10m'
    max_concurrent_requests: 1
    availability: 'not_checked'
    external_providers: []
    large_model_confirmed: boolean
  }
}

export interface SettingsResponse {
  provider: 'ollama'
  model: string
  context_length: number
  temperature: number
  max_output_tokens: number
  timeout_seconds: number
  keep_alive: '10m'
  ollama_endpoint: string
  max_concurrent_requests: 1
  large_model_confirmed: boolean
  availability: 'not_checked'
  external_providers: []
}

export interface ProjectRecord {
  id: string
  name: string
  path: string
  created_at: string
  updated_at: string
}

export interface ReviewRecord {
  id: string
  project_id: string
  status: string
  model: string
  created_at: string
  finding_count: number
  error_code: string | null
}

export interface QualityCheckRecord {
  id: string
  project_id: string
  status: string
  note: string | null
  created_at: string
}

export interface ReleaseReportRecord {
  id: string
  project_id: string
  title: string
  status: string
  note: string | null
  created_at: string
}

export function defaultBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured === 'string' && configured.trim() !== '') {
    return configured.trim().replace(/\/$/, '')
  }
  return 'http://127.0.0.1:8000'
}

export function assertLocalBaseUrl(value: string): string {
  let url: URL
  try {
    url = new URL(value)
  } catch {
    throw new ApiError('DevPilot only connects to a backend on localhost.')
  }
  if ((url.protocol !== 'http:' && url.protocol !== 'https:') || !isLoopbackHost(url.hostname)) {
    throw new ApiError(
      `Refusing ${value}. DevPilot only connects to a backend on localhost and will not use a hosted model.`,
    )
  }
  return value.replace(/\/$/, '')
}

function unreachable(baseUrl: string): string {
  return (
    `Cannot reach the DevPilot backend at ${baseUrl}. ` +
    'Start it with scripts/start.sh, then retry. ' +
    'DevPilot stays on the local Ollama model and will not switch to a hosted provider.'
  )
}

async function request(path: string, init?: RequestInit, baseUrl = defaultBaseUrl()): Promise<unknown> {
  const base = assertLocalBaseUrl(baseUrl)
  let response: Response
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      cache: 'no-store',
      credentials: 'omit',
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError(unreachable(base))
  }
  if (response.status === 422) {
    const payload: unknown = await response.json().catch(() => null)
    throw validationError(payload)
  }
  if (!response.ok) {
    throw new ApiError(
      `The local backend returned HTTP ${response.status}. Fix the backend, then retry. DevPilot will not switch to a hosted model.`,
    )
  }
  return response.json() as Promise<unknown>
}

function validationError(payload: unknown): ApiError {
  if (!isRecord(payload)) {
    return new ApiError('Settings were rejected.')
  }
  const errors = Array.isArray(payload.errors) ? payload.errors : []
  const fieldErrors = errors.flatMap((item) => {
    if (!isRecord(item) || typeof item.message !== 'string') {
      return []
    }
    return [{ field: typeof item.field === 'string' ? item.field : 'settings', message: item.message }]
  })
  const detail = fieldErrors.map((item) => item.message).join(' ')
  return new ApiError(detail || 'Settings were rejected.', fieldErrors)
}

export async function checkHealth(baseUrl?: string): Promise<HealthResponse> {
  const body = await request('/api/health', { method: 'GET' }, baseUrl ?? defaultBaseUrl())
  return parseHealth(body)
}

export async function readSettings(): Promise<SettingsResponse> {
  return parseSettings(await request('/api/settings', { method: 'GET' }))
}

export async function updateSettings(body: SettingsPayload): Promise<SettingsResponse> {
  return parseSettings(
    await request('/api/settings', { method: 'PATCH', body: JSON.stringify(body) }),
  )
}

export async function listProjects(): Promise<ProjectRecord[]> {
  return parseList(await request('/api/projects'), parseProject)
}

export async function listReviews(baseUrl?: string): Promise<ReviewRecord[]> {
  return parseList(
    await request('/api/reviews', { method: 'GET' }, baseUrl ?? defaultBaseUrl()),
    parseReview,
  )
}

export async function listQualityChecks(): Promise<QualityCheckRecord[]> {
  return parseList(await request('/api/quality-checks'), parseQuality)
}

export async function listReleaseReports(): Promise<ReleaseReportRecord[]> {
  return parseList(await request('/api/release-reports'), parseRelease)
}

function parseHealth(value: unknown): HealthResponse {
  if (!isRecord(value) || !isRecord(value.ai)) {
    throw new ApiError('The local backend returned an unreadable health response.')
  }
  const ai = value.ai
  if (ai.provider !== 'ollama' || !Array.isArray(ai.external_providers) || ai.external_providers.length > 0) {
    throw new ApiError('The backend reported an external AI provider. DevPilot will not continue.')
  }
  if (ai.availability !== 'not_checked') {
    throw new ApiError(
      'The backend reported an unexpected model status. DevPilot will not treat the model as available.',
    )
  }
  if (typeof ai.endpoint !== 'string' || endpointError(ai.endpoint)) {
    throw new ApiError('The backend reported an Ollama endpoint that is not on this machine.')
  }
  if (typeof value.bind_host !== 'string' || !isLoopbackHost(value.bind_host)) {
    throw new ApiError('The backend is not bound to localhost.')
  }
  if (value.status !== 'ok' && value.status !== 'degraded') {
    throw new ApiError('The local backend returned an unreadable health response.')
  }
  if (value.database !== 'ok' && value.database !== 'error') {
    throw new ApiError('The local backend returned an unreadable health response.')
  }
  return {
    status: value.status,
    version: typeof value.version === 'string' ? value.version : 'unknown',
    database: value.database,
    database_message: typeof value.database_message === 'string' ? value.database_message : null,
    bind_host: value.bind_host,
    ai: {
      provider: 'ollama',
      endpoint: ai.endpoint,
      model: typeof ai.model === 'string' ? ai.model : DEFAULT_MODEL_FALLBACK,
      context_length: numberField(ai.context_length),
      temperature: numberField(ai.temperature),
      max_output_tokens: numberField(ai.max_output_tokens),
      timeout_seconds: numberField(ai.timeout_seconds),
      keep_alive: '10m',
      max_concurrent_requests: 1,
      availability: 'not_checked',
      external_providers: [],
      large_model_confirmed: ai.large_model_confirmed === true,
    },
  }
}

const DEFAULT_MODEL_FALLBACK = 'qwen2.5-coder:7b'

function parseSettings(value: unknown): SettingsResponse {
  if (!isRecord(value) || value.provider !== 'ollama') {
    throw new ApiError('The backend reported an external AI provider. DevPilot will not continue.')
  }
  if (!Array.isArray(value.external_providers) || value.external_providers.length > 0) {
    throw new ApiError('The backend reported an external AI provider. DevPilot will not continue.')
  }
  if (typeof value.ollama_endpoint !== 'string' || endpointError(value.ollama_endpoint)) {
    throw new ApiError('The backend reported an Ollama endpoint that is not on this machine.')
  }
  if (value.availability !== 'not_checked') {
    throw new ApiError(
      'The backend reported an unexpected model status. DevPilot will not treat the model as available.',
    )
  }
  return {
    provider: 'ollama',
    model: typeof value.model === 'string' ? value.model : DEFAULT_MODEL_FALLBACK,
    context_length: numberField(value.context_length),
    temperature: numberField(value.temperature),
    max_output_tokens: numberField(value.max_output_tokens),
    timeout_seconds: numberField(value.timeout_seconds),
    keep_alive: '10m',
    ollama_endpoint: value.ollama_endpoint,
    max_concurrent_requests: 1,
    large_model_confirmed: value.large_model_confirmed === true,
    availability: 'not_checked',
    external_providers: [],
  }
}

function parseList<T>(value: unknown, parseItem: (item: unknown) => T): T[] {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    throw new ApiError('The local backend returned an unreadable list.')
  }
  return value.items.map(parseItem)
}

function parseProject(value: unknown): ProjectRecord {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.name !== 'string') {
    throw new ApiError('The local backend returned an unreadable repository row.')
  }
  return {
    id: value.id,
    name: value.name,
    path: typeof value.path === 'string' ? value.path : '',
    created_at: typeof value.created_at === 'string' ? value.created_at : '',
    updated_at: typeof value.updated_at === 'string' ? value.updated_at : '',
  }
}

function parseReview(value: unknown): ReviewRecord {
  if (!isRecord(value) || typeof value.id !== 'string') {
    throw new ApiError('The local backend returned an unreadable review row.')
  }
  return {
    id: value.id,
    project_id: typeof value.project_id === 'string' ? value.project_id : '',
    status: typeof value.status === 'string' ? value.status : 'pending',
    model: typeof value.model === 'string' ? value.model : '',
    created_at: typeof value.created_at === 'string' ? value.created_at : '',
    finding_count: numberField(value.finding_count),
    error_code: typeof value.error_code === 'string' ? value.error_code : null,
  }
}

function parseQuality(value: unknown): QualityCheckRecord {
  if (!isRecord(value) || typeof value.id !== 'string') {
    throw new ApiError('The local backend returned an unreadable quality-check row.')
  }
  return {
    id: value.id,
    project_id: typeof value.project_id === 'string' ? value.project_id : '',
    status: typeof value.status === 'string' ? value.status : 'pending',
    note: typeof value.note === 'string' ? value.note : null,
    created_at: typeof value.created_at === 'string' ? value.created_at : '',
  }
}

function parseRelease(value: unknown): ReleaseReportRecord {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.title !== 'string') {
    throw new ApiError('The local backend returned an unreadable release report.')
  }
  return {
    id: value.id,
    project_id: typeof value.project_id === 'string' ? value.project_id : '',
    title: value.title,
    status: typeof value.status === 'string' ? value.status : 'draft',
    note: typeof value.note === 'string' ? value.note : null,
    created_at: typeof value.created_at === 'string' ? value.created_at : '',
  }
}

function numberField(value: unknown): number {
  return typeof value === 'number' ? value : 0
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
