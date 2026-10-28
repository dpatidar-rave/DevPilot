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
  branch: string | null
  detached: boolean
  dirty: boolean
  magento: boolean
  inspection_error: string | null
}

export interface DirectoryListing {
  path: string
  parent: string | null
  directories: string[]
  truncated: boolean
}

export interface MagentoInfo {
  detected: boolean
  edition: string | null
  magento_version: string | null
  php_version: string | null
}

export interface RepositoryDetail {
  id: string
  name: string
  path: string
  branch: string | null
  detached: boolean
  head_sha: string | null
  head_subject: string | null
  committed_at: string | null
  branches: string[]
  dirty: boolean
  uncommitted_warning: string | null
  magento: MagentoInfo
}

export type DiffScope = 'staged' | 'unstaged' | 'committed' | 'untracked'

export interface ChangeFile {
  path: string
  status: string
  skipped: 'generated' | 'sensitive' | null
  selected: boolean
}

export interface ChangeSet {
  base: string | null
  branches: string[]
  staged: ChangeFile[]
  unstaged: ChangeFile[]
  committed: ChangeFile[]
  untracked: ChangeFile[]
  dirty: boolean
  truncated: boolean
  uncommitted_warning: string | null
  selected_paths: string[]
}

export interface DiffLine {
  kind: 'add' | 'delete' | 'context' | 'meta'
  text: string
  old_line: number | null
  new_line: number | null
}

export interface FileDiff {
  path: string
  scope: DiffScope
  binary: boolean
  truncated: boolean
  skipped: 'generated' | 'sensitive' | null
  language: string | null
  lines: DiffLine[]
}

export interface ReviewRecord {
  id: string
  project_id: string
  status: string
  base_ref: string | null
  head_ref: string | null
  model: string
  context_length: number
  created_at: string
  finding_count: number
  error_code: string | null
  error_message: string | null
  summary: string
  limitations: string[]
  skipped_files: { path: string; reason: string }[]
  reviewed_files: string[]
  files_reviewed: number
  files_skipped: number
  chunks_total: number
  chunks_completed: number
  temperature: number | null
  max_output_tokens: number | null
  timeout_seconds: number | null
  keep_alive: string | null
}

export interface ReviewFinding {
  id: string
  stable_key: string
  file_path: string
  scope: string
  start_line: number
  end_line: number
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  category: string
  title: string
  explanation: string
  evidence: string
  remediation: string
  confidence: number
  uncertain: boolean
  needs_human_verification: true
  evidence_checked: boolean
  origin: 'ai_suggestion'
}

export interface ReviewDetail extends ReviewRecord {
  findings: ReviewFinding[]
}

export type QualityResult = 'pass' | 'fail' | 'skipped' | 'timed_out'

export interface QualityCheckRecord {
  id: string
  project_id: string
  review_id: string | null
  status: string
  result: QualityResult | null
  tool: string | null
  command: string | null
  argv: string[]
  working_directory: string | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  exit_code: number | null
  stdout: string
  stderr: string
  output_truncated: boolean
  note: string | null
  created_at: string
  origin: 'command_result'
}

export interface QualityTool {
  tool: string
  label: string
  available: boolean
  files: string[]
  suggested_argv: string[]
  saved_argv: string[]
  reason: string | null
}

export interface QualityCatalog {
  project_id: string
  working_directory: string
  warning: string
  tools: QualityTool[]
}

export interface ReleaseReportRecord {
  id: string
  project_id: string
  review_id: string | null
  title: string
  status: string
  readiness: Readiness | null
  note: string | null
  head_sha: string | null
  created_at: string
}

export type Readiness = 'blocked' | 'needs_review' | 'ready_for_human_approval'
export type ChecklistStatus = 'pending' | 'passed' | 'failed' | 'waived' | 'not_applicable'

export interface ReleaseWaiver {
  text: string
  reason: string
  reviewer: string
}

export interface ChecklistItem {
  key: string
  label: string
  status: ChecklistStatus
  evidence: string
  reason: string
  reviewer: string
}

export interface FindingDisposition {
  id: string
  severity: string
  title: string
  file_path: string
  decision: string
  reason: string
  reviewer: string
}

export interface ReleaseAssessment {
  readiness: Readiness
  statement: string
  blockers: string[]
  warnings: string[]
  passed: string[]
  waivers: ReleaseWaiver[]
  missing: string[]
  checklist: ChecklistItem[]
  findings: FindingDisposition[]
  quality: { tool: string; result: string }[]
  model: {
    name: string
    context_length: number
    temperature: number
    max_output_tokens: number
    timeout_seconds: number
  }
  project_id: string
  project_name: string
  review_id: string
  review_status: string
  base_ref: string
  head_sha: string
  repository_head_sha: string
  dirty: boolean
  generated_at: string
  limitations: string[]
}

export interface ReleaseReportDetail extends ReleaseAssessment {
  id: string
  title: string
  status: string
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
    const parsed = validationError(payload)
    if (parsed.fieldErrors.length > 0) {
      throw parsed
    }
    if (isRecord(payload) && typeof payload.detail === 'string' && payload.detail.length < 400) {
      throw new ApiError(payload.detail)
    }
    throw parsed
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    if (isRecord(payload) && typeof payload.detail === 'string' && payload.detail.length < 400) {
      throw new ApiError(payload.detail)
    }
    throw new ApiError(
      `The local backend returned HTTP ${response.status}. Fix the backend, then retry. DevPilot will not switch to a hosted model.`,
    )
  }
  return response.json() as Promise<unknown>
}

async function requestText(path: string, baseUrl = defaultBaseUrl()): Promise<string> {
  const base = assertLocalBaseUrl(baseUrl)
  let response: Response
  try {
    response = await fetch(`${base}${path}`, {
      cache: 'no-store',
      credentials: 'omit',
      headers: { Accept: 'text/markdown, application/json' },
    })
  } catch {
    throw new ApiError(unreachable(base))
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    if (isRecord(payload) && typeof payload.detail === 'string' && payload.detail.length < 400) {
      throw new ApiError(payload.detail)
    }
    throw new ApiError(`The local backend returned HTTP ${response.status}.`)
  }
  return response.text()
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

export async function browseDirectories(path?: string): Promise<DirectoryListing> {
  const query = path ? `?${new URLSearchParams({ path })}` : ''
  return parseDirectory(await request(`/api/browse${query}`))
}

export async function registerProject(path: string, name?: string): Promise<RepositoryDetail> {
  const body: { path: string; name?: string } = { path }
  if (name && name.trim() !== '') {
    body.name = name.trim()
  }
  return parseRepository(await request('/api/projects', { method: 'POST', body: JSON.stringify(body) }))
}

export async function readProject(projectId: string): Promise<RepositoryDetail> {
  return parseRepository(await request(`/api/projects/${encodeURIComponent(projectId)}`))
}

export async function readChanges(projectId: string, base?: string): Promise<ChangeSet> {
  const query = base ? `?${new URLSearchParams({ base })}` : ''
  return parseChanges(await request(`/api/projects/${encodeURIComponent(projectId)}/changes${query}`))
}

export async function readFileDiff(
  projectId: string,
  scope: DiffScope,
  path: string,
  base?: string | null,
): Promise<FileDiff> {
  const params = new URLSearchParams({ scope, path })
  if (base) {
    params.set('base', base)
  }
  return parseDiff(
    await request(`/api/projects/${encodeURIComponent(projectId)}/diff?${params}`),
  )
}

export async function saveSelection(
  projectId: string,
  paths: string[],
  base: string | null,
): Promise<string[]> {
  const body = await request(`/api/projects/${encodeURIComponent(projectId)}/selection`, {
    method: 'PUT',
    body: JSON.stringify({ paths, base }),
  })
  if (!isRecord(body) || !Array.isArray(body.paths) || body.paths.some((item) => typeof item !== 'string')) {
    throw new ApiError('The local backend returned an unreadable selection.')
  }
  return body.paths
}

export async function listReviews(baseUrl?: string): Promise<ReviewRecord[]> {
  return parseList(
    await request('/api/reviews', { method: 'GET' }, baseUrl ?? defaultBaseUrl()),
    parseReview,
  )
}

export async function startReview(
  projectId: string,
  base: string,
  paths: string[],
): Promise<ReviewDetail> {
  return parseReviewDetail(
    await request('/api/reviews', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, base_ref: base, paths }),
    }),
  )
}

export async function readReview(reviewId: string): Promise<ReviewDetail> {
  return parseReviewDetail(await request(`/api/reviews/${encodeURIComponent(reviewId)}`))
}

export async function cancelReview(reviewId: string): Promise<ReviewDetail> {
  return parseReviewDetail(
    await request(`/api/reviews/${encodeURIComponent(reviewId)}/cancel`, { method: 'POST' }),
  )
}

export async function listQualityChecks(projectId?: string): Promise<QualityCheckRecord[]> {
  const query = projectId ? `?${new URLSearchParams({ project_id: projectId })}` : ''
  return parseList(await request(`/api/quality-checks${query}`), parseQuality)
}

export async function readQualityCatalog(projectId: string): Promise<QualityCatalog> {
  return parseCatalog(
    await request(`/api/projects/${encodeURIComponent(projectId)}/quality/tools`),
  )
}

export async function saveQualityCommand(
  projectId: string,
  tool: string,
  argv: string[],
): Promise<void> {
  await request(`/api/projects/${encodeURIComponent(projectId)}/quality/commands`, {
    method: 'PUT',
    body: JSON.stringify({ tool, argv }),
  })
}

export async function runQualityCheck(
  projectId: string,
  tool: string,
  confirmed: boolean,
  reviewId: string | null,
): Promise<QualityCheckRecord> {
  return parseQuality(
    await request(`/api/projects/${encodeURIComponent(projectId)}/quality/runs`, {
      method: 'POST',
      body: JSON.stringify({
        tool,
        confirmed,
        review_id: reviewId,
      }),
    }),
  )
}

export async function listReleaseReports(): Promise<ReleaseReportRecord[]> {
  return parseList(await request('/api/release-reports'), parseRelease)
}

export async function previewRelease(projectId: string, reviewId: string): Promise<ReleaseAssessment> {
  const query = new URLSearchParams({ review_id: reviewId })
  return parseAssessment(
    await request(`/api/projects/${encodeURIComponent(projectId)}/release-assessment?${query}`),
  )
}

export async function saveFindingDecision(
  reviewId: string,
  findingId: string,
  decision: string,
  reason: string,
  reviewer: string,
): Promise<ReleaseAssessment> {
  return parseAssessment(
    await request(
      `/api/reviews/${encodeURIComponent(reviewId)}/findings/${encodeURIComponent(findingId)}/decision`,
      {
        method: 'PUT',
        body: JSON.stringify({ decision, reason, reviewer }),
      },
    ),
  )
}

export async function saveChecklistDecision(
  reviewId: string,
  itemKey: string,
  status: ChecklistStatus,
  reason: string,
  reviewer: string,
): Promise<ReleaseAssessment> {
  return parseAssessment(
    await request(`/api/reviews/${encodeURIComponent(reviewId)}/checklist/${encodeURIComponent(itemKey)}`, {
      method: 'PUT',
      body: JSON.stringify({ status, reason, reviewer }),
    }),
  )
}

export async function createReleaseReport(projectId: string, reviewId: string): Promise<ReleaseReportDetail> {
  return parseReleaseDetail(
    await request('/api/release-reports', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, review_id: reviewId }),
    }),
  )
}

export async function readReleaseReport(reportId: string): Promise<ReleaseReportDetail> {
  return parseReleaseDetail(await request(`/api/release-reports/${encodeURIComponent(reportId)}`))
}

export async function downloadReleaseExport(reportId: string, format: 'markdown' | 'json'): Promise<void> {
  const text = await requestText(`/api/release-reports/${encodeURIComponent(reportId)}/${format}`)
  const blob = new Blob([text], {
    type: format === 'markdown' ? 'text/markdown;charset=utf-8' : 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = format === 'markdown' ? 'release-report.md' : 'release-report.json'
  link.click()
  URL.revokeObjectURL(url)
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
    branch: typeof value.branch === 'string' ? value.branch : null,
    detached: value.detached === true,
    dirty: value.dirty === true,
    magento: value.magento === true,
    inspection_error: typeof value.inspection_error === 'string' ? value.inspection_error : null,
  }
}

function parseDirectory(value: unknown): DirectoryListing {
  if (!isRecord(value) || typeof value.path !== 'string' || !Array.isArray(value.directories)) {
    throw new ApiError('The local backend returned an unreadable directory list.')
  }
  if (value.directories.some((item) => typeof item !== 'string')) {
    throw new ApiError('The local backend returned an unreadable directory list.')
  }
  return {
    path: value.path,
    parent: typeof value.parent === 'string' ? value.parent : null,
    directories: value.directories,
    truncated: value.truncated === true,
  }
}

function parseRepository(value: unknown): RepositoryDetail {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.name !== 'string') {
    throw new ApiError('The local backend returned an unreadable repository.')
  }
  return {
    id: value.id,
    name: value.name,
    path: typeof value.path === 'string' ? value.path : '',
    branch: typeof value.branch === 'string' ? value.branch : null,
    detached: value.detached === true,
    head_sha: typeof value.head_sha === 'string' ? value.head_sha : null,
    head_subject: typeof value.head_subject === 'string' ? value.head_subject : null,
    committed_at: typeof value.committed_at === 'string' ? value.committed_at : null,
    branches: stringList(value.branches),
    dirty: value.dirty === true,
    uncommitted_warning: typeof value.uncommitted_warning === 'string' ? value.uncommitted_warning : null,
    magento: parseMagento(value.magento),
  }
}

function parseMagento(value: unknown): MagentoInfo {
  if (!isRecord(value)) {
    throw new ApiError('The local backend returned an unreadable Magento status.')
  }
  return {
    detected: value.detected === true,
    edition: typeof value.edition === 'string' ? value.edition : null,
    magento_version: typeof value.magento_version === 'string' ? value.magento_version : null,
    php_version: typeof value.php_version === 'string' ? value.php_version : null,
  }
}

function parseChanges(value: unknown): ChangeSet {
  if (!isRecord(value)) {
    throw new ApiError('The local backend returned an unreadable change list.')
  }
  return {
    base: typeof value.base === 'string' ? value.base : null,
    branches: stringList(value.branches),
    staged: parseFiles(value.staged),
    unstaged: parseFiles(value.unstaged),
    committed: parseFiles(value.committed),
    untracked: parseFiles(value.untracked),
    dirty: value.dirty === true,
    truncated: value.truncated === true,
    uncommitted_warning: typeof value.uncommitted_warning === 'string' ? value.uncommitted_warning : null,
    selected_paths: stringList(value.selected_paths),
  }
}

function parseFiles(value: unknown): ChangeFile[] {
  if (!Array.isArray(value)) {
    throw new ApiError('The local backend returned an unreadable change list.')
  }
  return value.map((item) => {
    if (!isRecord(item) || typeof item.path !== 'string' || typeof item.status !== 'string') {
      throw new ApiError('The local backend returned an unreadable change list.')
    }
    const skipped = item.skipped === 'generated' || item.skipped === 'sensitive' ? item.skipped : null
    return { path: item.path, status: item.status, skipped, selected: item.selected === true }
  })
}

function parseDiff(value: unknown): FileDiff {
  if (!isRecord(value) || typeof value.path !== 'string' || !Array.isArray(value.lines)) {
    throw new ApiError('The local backend returned an unreadable diff.')
  }
  if (!isScope(value.scope)) {
    throw new ApiError('The local backend returned an unreadable diff.')
  }
  const skipped = value.skipped === 'generated' || value.skipped === 'sensitive' ? value.skipped : null
  return {
    path: value.path,
    scope: value.scope,
    binary: value.binary === true,
    truncated: value.truncated === true,
    skipped,
    language: typeof value.language === 'string' ? value.language : null,
    lines: value.lines.map(parseDiffLine),
  }
}

function parseDiffLine(value: unknown): DiffLine {
  if (!isRecord(value) || typeof value.text !== 'string' || !isDiffKind(value.kind)) {
    throw new ApiError('The local backend returned an unreadable diff.')
  }
  return {
    kind: value.kind,
    text: value.text,
    old_line: typeof value.old_line === 'number' ? value.old_line : null,
    new_line: typeof value.new_line === 'number' ? value.new_line : null,
  }
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    throw new ApiError('The local backend returned an unreadable list.')
  }
  return value
}

function isScope(value: unknown): value is DiffScope {
  return value === 'staged' || value === 'unstaged' || value === 'committed' || value === 'untracked'
}

function isDiffKind(value: unknown): value is DiffLine['kind'] {
  return value === 'add' || value === 'delete' || value === 'context' || value === 'meta'
}

function parseReview(value: unknown): ReviewRecord {
  if (!isRecord(value) || typeof value.id !== 'string') {
    throw new ApiError('The local backend returned an unreadable review row.')
  }
  return {
    id: value.id,
    project_id: typeof value.project_id === 'string' ? value.project_id : '',
    status: typeof value.status === 'string' ? value.status : 'pending',
    base_ref: typeof value.base_ref === 'string' ? value.base_ref : null,
    head_ref: typeof value.head_ref === 'string' ? value.head_ref : null,
    model: typeof value.model === 'string' ? value.model : '',
    context_length: numberField(value.context_length),
    created_at: typeof value.created_at === 'string' ? value.created_at : '',
    finding_count: numberField(value.finding_count),
    error_code: typeof value.error_code === 'string' ? value.error_code : null,
    error_message: typeof value.error_message === 'string' ? value.error_message : null,
    summary: typeof value.summary === 'string' ? value.summary : '',
    limitations: stringListOrEmpty(value.limitations),
    skipped_files: parseSkipped(value.skipped_files),
    reviewed_files: stringListOrEmpty(value.reviewed_files),
    files_reviewed: numberField(value.files_reviewed),
    files_skipped: numberField(value.files_skipped),
    chunks_total: numberField(value.chunks_total),
    chunks_completed: numberField(value.chunks_completed),
    temperature: typeof value.temperature === 'number' ? value.temperature : null,
    max_output_tokens: typeof value.max_output_tokens === 'number' ? value.max_output_tokens : null,
    timeout_seconds: typeof value.timeout_seconds === 'number' ? value.timeout_seconds : null,
    keep_alive: typeof value.keep_alive === 'string' ? value.keep_alive : null,
  }
}

function parseReviewDetail(value: unknown): ReviewDetail {
  const review = parseReview(value)
  if (!isRecord(value) || !Array.isArray(value.findings)) {
    throw new ApiError('The local backend returned an unreadable review.')
  }
  return { ...review, findings: value.findings.map(parseFinding) }
}

function parseFinding(value: unknown): ReviewFinding {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.title !== 'string') {
    throw new ApiError('The local backend returned an unreadable finding.')
  }
  if (value.origin !== 'ai_suggestion' || value.needs_human_verification !== true) {
    throw new ApiError('A finding was not labeled as an AI suggestion.')
  }
  const severity = value.severity
  if (
    severity !== 'critical' &&
    severity !== 'high' &&
    severity !== 'medium' &&
    severity !== 'low' &&
    severity !== 'info'
  ) {
    throw new ApiError('The local backend returned an unreadable finding.')
  }
  return {
    id: value.id,
    stable_key: typeof value.stable_key === 'string' ? value.stable_key : value.id,
    file_path: typeof value.file_path === 'string' ? value.file_path : '',
    scope: typeof value.scope === 'string' ? value.scope : '',
    start_line: numberField(value.start_line),
    end_line: numberField(value.end_line),
    severity,
    category: typeof value.category === 'string' ? value.category : '',
    title: value.title,
    explanation: typeof value.explanation === 'string' ? value.explanation : '',
    evidence: typeof value.evidence === 'string' ? value.evidence : '',
    remediation: typeof value.remediation === 'string' ? value.remediation : '',
    confidence: numberField(value.confidence),
    uncertain: value.uncertain === true,
    needs_human_verification: true,
    evidence_checked: value.evidence_checked === true,
    origin: 'ai_suggestion',
  }
}

function parseSkipped(value: unknown): { path: string; reason: string }[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.flatMap((item) => {
    if (!isRecord(item) || typeof item.path !== 'string') {
      return []
    }
    return [{ path: item.path, reason: typeof item.reason === 'string' ? item.reason : '' }]
  })
}

function stringListOrEmpty(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string')
}

function parseQuality(value: unknown): QualityCheckRecord {
  if (!isRecord(value) || typeof value.id !== 'string') {
    throw new ApiError('The local backend returned an unreadable quality-check row.')
  }
  const result = qualityResult(value.result)
  return {
    id: value.id,
    project_id: typeof value.project_id === 'string' ? value.project_id : '',
    review_id: typeof value.review_id === 'string' ? value.review_id : null,
    status: typeof value.status === 'string' ? value.status : 'pending',
    result,
    tool: typeof value.tool === 'string' ? value.tool : null,
    command: typeof value.command === 'string' ? value.command : null,
    argv: stringListOrEmpty(value.argv),
    working_directory: typeof value.working_directory === 'string' ? value.working_directory : null,
    started_at: typeof value.started_at === 'string' ? value.started_at : null,
    finished_at: typeof value.finished_at === 'string' ? value.finished_at : null,
    duration_ms: typeof value.duration_ms === 'number' ? value.duration_ms : null,
    exit_code: typeof value.exit_code === 'number' ? value.exit_code : null,
    stdout: typeof value.stdout === 'string' ? value.stdout : '',
    stderr: typeof value.stderr === 'string' ? value.stderr : '',
    output_truncated: value.output_truncated === true,
    note: typeof value.note === 'string' ? value.note : null,
    created_at: typeof value.created_at === 'string' ? value.created_at : '',
    origin: 'command_result',
  }
}

function parseCatalog(value: unknown): QualityCatalog {
  if (!isRecord(value) || !Array.isArray(value.tools) || typeof value.project_id !== 'string') {
    throw new ApiError('The local backend returned an unreadable quality-check catalog.')
  }
  return {
    project_id: value.project_id,
    working_directory: typeof value.working_directory === 'string' ? value.working_directory : '',
    warning: typeof value.warning === 'string' ? value.warning : '',
    tools: value.tools.map(parseTool),
  }
}

function parseTool(value: unknown): QualityTool {
  if (!isRecord(value) || typeof value.tool !== 'string' || typeof value.label !== 'string') {
    throw new ApiError('The local backend returned an unreadable quality-check tool.')
  }
  return {
    tool: value.tool,
    label: value.label,
    available: value.available === true,
    files: stringListOrEmpty(value.files),
    suggested_argv: stringListOrEmpty(value.suggested_argv),
    saved_argv: stringListOrEmpty(value.saved_argv),
    reason: typeof value.reason === 'string' ? value.reason : null,
  }
}

function qualityResult(value: unknown): QualityResult | null {
  if (value === 'pass' || value === 'fail' || value === 'skipped' || value === 'timed_out') {
    return value
  }
  return null
}

function parseRelease(value: unknown): ReleaseReportRecord {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.title !== 'string') {
    throw new ApiError('The local backend returned an unreadable release report.')
  }
  return {
    id: value.id,
    project_id: typeof value.project_id === 'string' ? value.project_id : '',
    review_id: typeof value.review_id === 'string' ? value.review_id : null,
    title: value.title,
    status: typeof value.status === 'string' ? value.status : 'draft',
    readiness: readinessOrNull(value.readiness),
    note: typeof value.note === 'string' ? value.note : null,
    head_sha: typeof value.head_sha === 'string' ? value.head_sha : null,
    created_at: typeof value.created_at === 'string' ? value.created_at : '',
  }
}

function parseReleaseDetail(value: unknown): ReleaseReportDetail {
  const assessment = parseAssessment(value)
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.title !== 'string') {
    throw new ApiError('The local backend returned an unreadable release report.')
  }
  return {
    ...assessment,
    id: value.id,
    title: value.title,
    status: typeof value.status === 'string' ? value.status : 'draft',
  }
}

function parseAssessment(value: unknown): ReleaseAssessment {
  if (!isRecord(value) || !isRecord(value.model) || typeof value.statement !== 'string') {
    throw new ApiError('The local backend returned an unreadable release report.')
  }
  const readiness = readinessOrNull(value.readiness)
  if (readiness === null) {
    throw new ApiError('The local backend returned an unreadable release report.')
  }
  return {
    readiness,
    statement: value.statement,
    blockers: stringListOrEmpty(value.blockers),
    warnings: stringListOrEmpty(value.warnings),
    passed: stringListOrEmpty(value.passed),
    waivers: Array.isArray(value.waivers) ? value.waivers.map(parseWaiver) : [],
    missing: stringListOrEmpty(value.missing),
    checklist: Array.isArray(value.checklist) ? value.checklist.map(parseChecklistItem) : [],
    findings: Array.isArray(value.findings) ? value.findings.map(parseDisposition) : [],
    quality: Array.isArray(value.quality) ? value.quality.map(parseQualityEvidence) : [],
    model: {
      name: typeof value.model.name === 'string' ? value.model.name : '',
      context_length: numberField(value.model.context_length),
      temperature: numberField(value.model.temperature),
      max_output_tokens: numberField(value.model.max_output_tokens),
      timeout_seconds: numberField(value.model.timeout_seconds),
    },
    project_id: typeof value.project_id === 'string' ? value.project_id : '',
    project_name: typeof value.project_name === 'string' ? value.project_name : '',
    review_id: typeof value.review_id === 'string' ? value.review_id : '',
    review_status: typeof value.review_status === 'string' ? value.review_status : '',
    base_ref: typeof value.base_ref === 'string' ? value.base_ref : '',
    head_sha: typeof value.head_sha === 'string' ? value.head_sha : '',
    repository_head_sha: typeof value.repository_head_sha === 'string' ? value.repository_head_sha : '',
    dirty: value.dirty === true,
    generated_at: typeof value.generated_at === 'string' ? value.generated_at : '',
    limitations: stringListOrEmpty(value.limitations),
  }
}

function parseWaiver(value: unknown): ReleaseWaiver {
  if (!isRecord(value) || typeof value.text !== 'string') {
    throw new ApiError('The local backend returned an unreadable release report.')
  }
  return {
    text: value.text,
    reason: typeof value.reason === 'string' ? value.reason : '',
    reviewer: typeof value.reviewer === 'string' ? value.reviewer : '',
  }
}

function parseChecklistItem(value: unknown): ChecklistItem {
  if (!isRecord(value) || typeof value.key !== 'string' || typeof value.label !== 'string') {
    throw new ApiError('The local backend returned an unreadable release report.')
  }
  const status = checklistStatus(value.status)
  return {
    key: value.key,
    label: value.label,
    status,
    evidence: typeof value.evidence === 'string' ? value.evidence : '',
    reason: typeof value.reason === 'string' ? value.reason : '',
    reviewer: typeof value.reviewer === 'string' ? value.reviewer : '',
  }
}

function parseDisposition(value: unknown): FindingDisposition {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.title !== 'string') {
    throw new ApiError('The local backend returned an unreadable release report.')
  }
  return {
    id: value.id,
    severity: typeof value.severity === 'string' ? value.severity : '',
    title: value.title,
    file_path: typeof value.file_path === 'string' ? value.file_path : '',
    decision: typeof value.decision === 'string' ? value.decision : '',
    reason: typeof value.reason === 'string' ? value.reason : '',
    reviewer: typeof value.reviewer === 'string' ? value.reviewer : '',
  }
}

function parseQualityEvidence(value: unknown): { tool: string; result: string } {
  if (!isRecord(value) || typeof value.tool !== 'string' || typeof value.result !== 'string') {
    throw new ApiError('The local backend returned an unreadable release report.')
  }
  return { tool: value.tool, result: value.result }
}

function readinessOrNull(value: unknown): Readiness | null {
  if (value === 'blocked' || value === 'needs_review' || value === 'ready_for_human_approval') {
    return value
  }
  return null
}

function checklistStatus(value: unknown): ChecklistStatus {
  if (
    value === 'pending' ||
    value === 'passed' ||
    value === 'failed' ||
    value === 'waived' ||
    value === 'not_applicable'
  ) {
    return value
  }
  throw new ApiError('The local backend returned an unreadable release report.')
}

function numberField(value: unknown): number {
  return typeof value === 'number' ? value : 0
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
