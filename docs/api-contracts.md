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

## Defined for later phases, not mounted

These Pydantic models live in `backend/app/schemas/` and reject extra fields. No route accepts them yet.

- `ProjectCreate` requires an absolute local path.
- `ReviewCreate` accepts `project_id`, `base_ref`, and `head_ref`. It does not accept a provider or a model override.
- `FindingContract` requires `uncertain: true` when `confidence` is below 0.5.
- `QualityCheckCreate` and `ReleaseReportCreate` describe later runs.

Creating a review, cancelling a review, running a quality check, generating a release report, and running the benchmark are not implemented.
