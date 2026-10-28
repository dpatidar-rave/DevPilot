# API contracts

The base URL is `http://127.0.0.1:8000`. OpenAPI is served at `/api/openapi.json`. `/docs` and `/redoc` are disabled.

## Implemented in Phase 0

### `GET /api/health`

Does not contact Ollama.

```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "ok",
  "database_message": null,
  "bind_host": "127.0.0.1",
  "ai": {
    "provider": "ollama",
    "endpoint": "http://127.0.0.1:11434",
    "model": "qwen2.5-coder:7b",
    "context_length": 8192,
    "temperature": 0.1,
    "max_output_tokens": 1800,
    "timeout_seconds": 180,
    "keep_alive": "10m",
    "max_concurrent_requests": 1,
    "availability": "not_checked",
    "external_providers": [],
    "large_model_confirmed": false
  }
}
```

`availability` stays `not_checked` until a future review explicitly probes Ollama. SQLite failure returns HTTP 503 and `"status": "degraded"`.

### `GET /api/settings` and `PATCH /api/settings`

Patchable fields: `model`, `context_length`, `temperature`, `max_output_tokens`, `timeout_seconds`, `ollama_endpoint`, `large_model_confirmed`.

There is no provider field. Unknown fields, hosted model names, non-loopback endpoints, and a 20B-or-larger model without confirmation return HTTP 422:

```json
{
  "detail": "Settings were rejected.",
  "errors": [{ "field": "model", "message": "Hosted model names are not allowed." }]
}
```

The response body does not echo the rejected value.

### Read-only lists

`GET /api/projects`, `GET /api/reviews`, `GET /api/quality-checks`, and `GET /api/release-reports` return `{ "items": [] }` when the database has no rows. They do not create sample data.

## Implemented in Phase 1

All of these stay on the registered work tree. A Git failure returns a short message and does not include command output that could contain source.

### `GET /api/browse?path=`

Lists child directories of an absolute local path. The default is the user home directory. Dot-directories and symlinks are skipped. The response is `{ "path", "parent", "directories", "truncated" }`.

### `POST /api/projects`

Body: `{ "path": "/absolute/work/tree", "name": "optional" }`. The path must be a Git working tree. HTTP 201 returns the repository detail. A duplicate path is HTTP 409. A missing path or a non-Git directory is HTTP 400. A relative path is HTTP 422.

### `GET /api/projects` and `GET /api/projects/{id}`

The list items include `branch`, `detached`, `dirty`, `magento`, and `inspection_error`. A stored path that is no longer a work tree returns the stored name and path with `inspection_error` instead of failing the whole list. The detail adds `head_sha`, `head_subject`, `committed_at`, `branches`, `uncommitted_warning`, and `magento.edition`, `magento.magento_version`, and `magento.php_version`. Versions are null unless they were established exactly.

### `GET /api/projects/{id}/changes?base=`

`base` must be one of the repository's local branches. The response separates `staged`, `unstaged`, `committed`, and `untracked`. Each file has `path`, `status`, `skipped` (`generated`, `sensitive`, or null), and `selected`. `selected_paths` is the saved review selection. `uncommitted_warning` is present when the work tree is dirty.

### `GET /api/projects/{id}/diff?scope=&path=&base=`

`scope` is `staged`, `unstaged`, `committed`, or `untracked`. The path must already appear in that change group. Lines are `add`, `delete`, `context`, or `meta`, with `old_line` and `new_line`. A generated or sensitive path returns `skipped` and an empty `lines` array. Large diffs set `truncated`.

### `PUT /api/projects/{id}/selection`

Body: `{ "paths": ["app/code/Example.php"], "base": "main" }`. Only paths visible in the current change set are stored. A path outside that set is HTTP 422, and the response does not echo the path.

## Implemented in Phase 2

The model name and Ollama origin come from local settings. A request cannot choose a provider or a model.

### `POST /api/reviews`

Body: `{ "project_id", "base_ref", "paths" }`. HTTP 201 returns the review, including `model`, temperature, context, the comparison, files reviewed, files skipped, limitations, and findings. A provider or model field is HTTP 422. A missing repository is HTTP 404. A second review of the same repository while one is running is HTTP 409.

### `GET /api/reviews` and `GET /api/reviews/{id}`

The list is the local history. The detail adds findings. Every finding has `origin: "ai_suggestion"` and `needs_human_verification: true`. `evidence_checked` is true only when the quote and line range were present in the chunk sent to the model.

### `POST /api/reviews/{id}/cancel`

Marks a running review cancelled. The in-flight local request is discarded when it returns. Cancelling a finished review is HTTP 409.

`error_code` is a short local code such as `timeout`, `model_missing`, `unavailable`, `busy`, or `interrupted`. `error_message` tells the user to retry locally. The body does not include the prompt or the model response.

## Implemented in Phase 3

Quality checks are command results. They are not AI suggestions. No route accepts a shell string or an argument list from a model response.

### `GET /api/projects/{id}/quality/tools`

Reports PHP_CodeSniffer, PHPStan, PHPUnit, Composer validation, and the Magento CLI when their known files exist. The response includes `working_directory`, a side-effect `warning`, and each tool's `files`, `suggested_argv`, `saved_argv`, `available`, and `reason`. This request does not start a process.

### `PUT /api/projects/{id}/quality/commands`

Body: `{ "tool", "argv" }`. `argv` is a list of strings. The command is stored for that repository after the allowlist accepts it. The response is the saved command. It is not executed.

### `POST /api/projects/{id}/quality/runs`

Body: `{ "tool", "confirmed": true, "review_id": null }`. `confirmed` must be true. `review_id`, when set, must already belong to the same repository. Extra fields are HTTP 422. The response is one check row: `command`, `working_directory`, `started_at`, `duration_ms`, `exit_code`, `stdout`, `stderr`, `output_truncated`, and `result` (`pass`, `fail`, `skipped`, or `timed_out`). `origin` is `command_result`.

### `GET /api/quality-checks?project_id=`

Lists stored rows, newest first. `project_id` is optional.

## Defined for later phases, not mounted

These Pydantic models live in `backend/app/schemas/` and reject extra fields. No route accepts them yet.

- `FindingContract` requires `uncertain: true` when `confidence` is below 0.5.
- `ReleaseReportCreate` describes a later release report.

Generating a release report and running the benchmark are not implemented. Quality-check rows stay separate from AI suggestions.
