# Architecture

DevPilot is a local-first review assistant. Phase 1 adds read-only Git inspection on top of the Phase 0 shell. It does not run a review and it does not call Ollama.

```mermaid
flowchart LR
  UI["React UI\n127.0.0.1:5173"] --> API["FastAPI\n127.0.0.1:8000"]
  API --> DB["SQLite"]
  API --> LOG["Local JSON logs"]
  API -. later review .-> MODEL["ModelGateway"]
  MODEL -. explicit review only .-> OLLAMA["Ollama\n127.0.0.1:11434"]
  REVIEW["ReviewService"] --> MODEL
  REVIEW --> DB
  REPO["RepositoryService"] --> GIT["git read-only argv"]
```

## Services

| Service | Responsibility |
| --- | --- |
| `RepositoryService` | Registers a local work tree, inspects branches and status, and reads diffs. Every `git` invocation is an allowlisted argument list pinned to that work tree. `prepare()` still validates an argument list without executing it. |
| `ReviewService` | Depends on the `InferenceClient` protocol, not on a concrete model. It does not start a review. |
| `ModelGateway` | Builds a local Ollama client with proxy use and redirects disabled. Construction and `open_client()` do not send a request. |
| `QualityCheckService` | Reads stored quality-check rows. |
| `ReleaseReportService` | Reads stored release-report rows. |
| `Persistence` helpers | Ping SQLite and list stored rows. Nothing is seeded. |

A later model is selected by changing `DEVPILOT_MODEL` or the settings page. `ReviewService` does not import Ollama.

## Process boundaries

- The API binds only to `127.0.0.1`, `localhost`, or `::1`. `0.0.0.0` is rejected.
- CORS allows the configured loopback UI origin and its `localhost` / `127.0.0.1` alias. There is no `*` origin.
- The Ollama URL must resolve only to loopback addresses. Hosted host names are rejected before DNS.
- Hosted model names are rejected. A model at 20B parameters or larger requires `large_model_confirmed=true`.
- The database URL must be a SQLite file. Remote databases are rejected.
- Interactive API docs are off so the browser does not load a documentation CDN.
- Logs are JSON on disk, mode `0600`. Secret-shaped text, prompts, diffs, and model responses are redacted or dropped.

## What this build does not do

- It does not start a review, chunk a diff for a model, or score findings.
- It does not call Ollama, pull a model, or fall back to a hosted model.
- It does not execute shell text, patches, or text returned by a model or by repository files.
- It does not commit, push, merge, reset, clean, checkout, or switch branches.
- It does not insert sample findings.
- It does not read `.env`, `app/etc/env.php`, private keys, or other credential-shaped files, and it does not load generated directories into the diff viewer.
