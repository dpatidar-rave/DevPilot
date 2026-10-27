export const LOCAL_API_ORIGIN = "http://127.0.0.1:8000";

export type ModelConfiguration = {
  name: string;
  context_length: number;
  temperature: number;
  max_output_tokens: number;
  timeout_seconds: number;
  keep_alive: string;
  endpoint: string;
  availability: string;
  large_model: boolean;
  memory_warning: string | null;
};

export type DatabaseState = {
  ready: boolean;
  error: string | null;
  retry: string[];
};

export type SystemStatus = {
  api: string;
  bind_host: string;
  ai_provider: string;
  fallback_used: boolean;
  database: DatabaseState;
  model: ModelConfiguration;
};

export type StoredReview = {
  id: number;
  created_at: string;
  repository_path: string;
  status: string;
  summary: string;
};

export type ReleaseReport = {
  records: StoredReview[];
  summary: string;
  ai_provider: string;
  fallback_used: boolean;
};

export type QualityCheck = {
  check_id: string;
  description: string;
  execution: string;
  requires_explicit_approval: boolean;
  executed: boolean;
};

export type Inspection = {
  path: string;
  read_only: boolean;
  inside_work_tree: boolean;
  branch: string;
  status_porcelain: string;
  truncated: boolean;
};

export type ReviewFinding = {
  path: string;
  line_start: number;
  line_end: number;
  severity: string;
  category: string;
  summary: string;
  confidence: string;
  uncertain: boolean;
};

export type ReviewJob = {
  id: string;
  status: string;
  repository_path: string;
  message: string;
  findings: ReviewFinding[];
  errors: string[];
  setup_instruction: string | null;
  retry: string[];
};

export type DashboardData = {
  system: SystemStatus;
  checks: QualityCheck[];
  reviews: StoredReview[] | null;
  report: ReleaseReport | null;
};

const API_UNREACHABLE =
  "Cannot reach the DevPilot API on this machine. Start it with `python -m app` from the backend directory, then retry. DevPilot does not use a hosted API.";

export function assertLoopbackApiBase(url: string): void {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error("DevPilot only calls a localhost API.");
  }
  const host = parsed.hostname;
  const loopback = host === "127.0.0.1" || host === "localhost" || host === "[::1]" || host === "::1";
  if (!loopback || parsed.protocol !== "http:") {
    throw new Error("DevPilot only calls a localhost API.");
  }
}

export function assertLocalProvider(status: { ai_provider: string; fallback_used: boolean }): void {
  if (status.fallback_used || status.ai_provider !== "ollama-local") {
    throw new Error("DevPilot refused a non-local model provider.");
  }
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  if (!path.startsWith("/api/") || path.startsWith("//") || path.includes("..")) {
    throw new Error("Refusing to call a non-local DevPilot API path.");
  }
  try {
    return await fetch(path, init);
  } catch {
    throw new Error(API_UNREACHABLE);
  }
}

export async function loadDashboard(): Promise<DashboardData> {
  const system = parseSystemStatus(await readJson(await apiFetch("/api/system/status")));
  assertLocalProvider(system);
  const checks = parseChecks(await readJson(await apiFetch("/api/quality-checks")));
  if (!system.database.ready) {
    return { system, checks, reviews: null, report: null };
  }
  const reviews = parseReviews(await readJson(await apiFetch("/api/reviews")));
  const report = parseReport(await readJson(await apiFetch("/api/release-report")));
  assertLocalProvider(report);
  return { system, checks, reviews, report };
}

export async function inspectRepository(path: string): Promise<Inspection> {
  const response = await apiFetch("/api/repository/inspect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, approved: true }),
  });
  return parseInspection(await readJson(response));
}

export async function startReview(path: string, confirmLargeModel: boolean): Promise<ReviewJob> {
  const response = await apiFetch("/api/reviews/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, approved: true, confirm_large_model: confirmLargeModel }),
  });
  return parseJob(await readJson(response));
}

export async function fetchReviewJob(id: string): Promise<ReviewJob> {
  return parseJob(await readJson(await apiFetch(`/api/reviews/jobs/${encodeURIComponent(id)}`)));
}

export async function cancelReviewJob(id: string): Promise<ReviewJob> {
  return parseJob(
    await readJson(
      await apiFetch(`/api/reviews/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
    ),
  );
}

async function readJson(response: Response): Promise<unknown> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error(response.ok ? "The local API returned an unexpected response." : API_UNREACHABLE);
  }
  if (!response.ok) {
    throw new Error(messageFrom(payload));
  }
  return payload;
}

function messageFrom(payload: unknown): string {
  if (typeof payload === "object" && payload !== null && "message" in payload) {
    const message = payload.message;
    if (typeof message === "string" && message.trim() !== "") {
      return message;
    }
  }
  return "The local DevPilot API returned an error. Restart `python -m app` and retry.";
}

function parseSystemStatus(payload: unknown): SystemStatus {
  const record = asRecord(payload, "system status");
  const database = asRecord(record.database, "database");
  const model = asRecord(record.model, "model");
  return {
    api: asString(record.api, "api"),
    bind_host: asString(record.bind_host, "bind_host"),
    ai_provider: asString(record.ai_provider, "ai_provider"),
    fallback_used: asBoolean(record.fallback_used, "fallback_used"),
    database: {
      ready: asBoolean(database.ready, "database.ready"),
      error: asNullableString(database.error, "database.error"),
      retry: asStringList(database.retry, "database.retry"),
    },
    model: {
      name: asString(model.name, "model.name"),
      context_length: asNumber(model.context_length, "model.context_length"),
      temperature: asNumber(model.temperature, "model.temperature"),
      max_output_tokens: asNumber(model.max_output_tokens, "model.max_output_tokens"),
      timeout_seconds: asNumber(model.timeout_seconds, "model.timeout_seconds"),
      keep_alive: asString(model.keep_alive, "model.keep_alive"),
      endpoint: asString(model.endpoint, "model.endpoint"),
      availability: asString(model.availability, "model.availability"),
      large_model: asBoolean(model.large_model, "model.large_model"),
      memory_warning: asNullableString(model.memory_warning, "model.memory_warning"),
    },
  };
}

function parseChecks(payload: unknown): QualityCheck[] {
  const record = asRecord(payload, "quality checks");
  if (!Array.isArray(record.checks)) {
    throw new Error("The local API returned an unexpected response.");
  }
  return record.checks.map((item) => {
    const check = asRecord(item, "quality check");
    return {
      check_id: asString(check.check_id, "check_id"),
      description: asString(check.description, "description"),
      execution: asString(check.execution, "execution"),
      requires_explicit_approval: asBoolean(check.requires_explicit_approval, "requires_explicit_approval"),
      executed: asBoolean(check.executed, "executed"),
    };
  });
}

function parseReviews(payload: unknown): StoredReview[] {
  const record = asRecord(payload, "reviews");
  if (!Array.isArray(record.reviews)) {
    throw new Error("The local API returned an unexpected response.");
  }
  return record.reviews.map(parseReview);
}

function parseReport(payload: unknown): ReleaseReport {
  const record = asRecord(payload, "release report");
  if (!Array.isArray(record.records)) {
    throw new Error("The local API returned an unexpected response.");
  }
  return {
    records: record.records.map(parseReview),
    summary: asString(record.summary, "summary"),
    ai_provider: asString(record.ai_provider, "ai_provider"),
    fallback_used: asBoolean(record.fallback_used, "fallback_used"),
  };
}

function parseReview(payload: unknown): StoredReview {
  const record = asRecord(payload, "review");
  return {
    id: asNumber(record.id, "id"),
    created_at: asString(record.created_at, "created_at"),
    repository_path: asString(record.repository_path, "repository_path"),
    status: asString(record.status, "status"),
    summary: asString(record.summary, "summary"),
  };
}

function parseInspection(payload: unknown): Inspection {
  const record = asRecord(payload, "inspection");
  return {
    path: asString(record.path, "path"),
    read_only: asBoolean(record.read_only, "read_only"),
    inside_work_tree: asBoolean(record.inside_work_tree, "inside_work_tree"),
    branch: asString(record.branch, "branch"),
    status_porcelain: asString(record.status_porcelain, "status_porcelain"),
    truncated: asBoolean(record.truncated, "truncated"),
  };
}

function parseJob(payload: unknown): ReviewJob {
  const record = asRecord(payload, "review job");
  return {
    id: asString(record.id, "id"),
    status: asString(record.status, "status"),
    repository_path: asString(record.repository_path, "repository_path"),
    message: asString(record.message, "message"),
    findings: Array.isArray(record.findings) ? record.findings.map(parseFinding) : [],
    errors: asStringList(record.errors, "errors"),
    setup_instruction: asNullableString(record.setup_instruction, "setup_instruction"),
    retry: asStringList(record.retry, "retry"),
  };
}

function parseFinding(payload: unknown): ReviewFinding {
  const record = asRecord(payload, "finding");
  return {
    path: asString(record.path, "path"),
    line_start: asNumber(record.line_start, "line_start"),
    line_end: asNumber(record.line_end, "line_end"),
    severity: asString(record.severity, "severity"),
    category: asString(record.category, "category"),
    summary: asString(record.summary, "summary"),
    confidence: asString(record.confidence, "confidence"),
    uncertain: asBoolean(record.uncertain, "uncertain"),
  };
}

function asRecord(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`The local API returned an unexpected ${label}.`);
  }
  return value as Record<string, unknown>;
}

function asString(value: unknown, label: string): string {
  if (typeof value !== "string") {
    throw new Error(`The local API response is missing ${label}.`);
  }
  return value;
}

function asNullableString(value: unknown, label: string): string | null {
  if (value === null) {
    return null;
  }
  return asString(value, label);
}

function asBoolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") {
    throw new Error(`The local API response is missing ${label}.`);
  }
  return value;
}

function asNumber(value: unknown, label: string): number {
  if (typeof value !== "number") {
    throw new Error(`The local API response is missing ${label}.`);
  }
  return value;
}

function asStringList(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new Error(`The local API response is missing ${label}.`);
  }
  return value;
}
