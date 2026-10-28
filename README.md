# DevPilot

DevPilot is a local-first code review and release-quality assistant for a Magento 2 / Adobe Commerce agency. Phase 2 reviews a selected diff with a local Ollama model. Phase 3 runs PHP and Magento commands that you configure and confirm for each repository. Findings are AI suggestions. Quality-check rows are command results. Neither is a guaranteed defect.

Source code, git diffs, findings, and the database stay on this machine. Inference is reserved for a locally running Ollama model. There is no hosted-model fallback.

## Privacy boundaries

- The API binds to loopback (`127.0.0.1` by default). It refuses `0.0.0.0` and other public hosts.
- The UI dev server binds to `127.0.0.1`. Open `http://127.0.0.1:5173`.
- CORS allows only the local UI origin.
- The only model provider is Ollama. The endpoint must resolve to a loopback address.
- Hosted model names are rejected. `qwen2.5-coder:7b` is the default on a 16 GB Apple silicon Mac.
- A model at 20B parameters or larger is an optional experiment. Set `large_model_confirmed=true` only after accepting the extra memory use.
- The app does not call Ollama until you start a review. Health and settings never probe the model.
- The app does not download models. If the selected model is missing, pull it yourself.
- Git inspection is read-only. The app does not commit, push, merge, reset, clean, or switch branches. Git commands are argument lists pinned to a registered work tree. Hooks, aliases, and external diff programs are not used.
- Commands, patches, and shell text from a model or from repository files are untrusted data and are not executed.
- Logs are local JSON files. They redact credentials and drop prompts, diffs, source, and model responses.
- There is no cloud analytics, telemetry, remote logging, or error reporting. FastAPI's built-in tracing, metrics, and logs are turned off, and the OpenTelemetry exporter is not installed. API docs that would load a CDN are disabled.
- SQLite is the only database. The file mode is `0600`.

## Prerequisites

- macOS
- Python 3.11 or newer
- Node.js 20 or newer
- Ollama, installed by you, for a later review phase

## Setup

```bash
scripts/setup.sh
```

The script creates `backend/.venv`, installs the API and UI dependencies, copies `.env.example` to `.env` when needed, and creates the SQLite database. It does not start Ollama and it does not pull a model.

When you are ready to use a later review phase:

```bash
brew install ollama
brew services start ollama
ollama pull qwen2.5-coder:7b
```

## Start

```bash
scripts/start.sh
```

- UI: `http://127.0.0.1:5173`
- API health: `http://127.0.0.1:8000/api/health`

Press Ctrl+C to stop both processes. If the UI cannot reach the API, the Overview page shows the error and a Retry button. That failure stays local. DevPilot will not switch providers.

## Repository explorer

Open `http://127.0.0.1:5173/repositories` and register an absolute path to a Git working tree. The UI lists the current branch, latest commit, local branches, staged changes, unstaged changes, committed differences against a base branch, and untracked files. File diffs use syntax highlighting and mark added and deleted lines. The selection you save is stored in SQLite. Open it from the repository page to start a local review.

Magento is detected from `composer.json` and `app/etc/di.xml`. PHP and Magento versions appear only when those files contain an exact version, not a range.

Credential-shaped files and generated directories are listed and are not opened. Manual steps and the safety rules are in [docs/repository-explorer.md](docs/repository-explorer.md).

## Local review

Open `http://127.0.0.1:5173/reviews/new`. Choose a registered repository, a base branch, and the changed files. DevPilot builds a manifest, skips secrets, binaries, generated files, and ignore patterns, and sends each chunk only to the Ollama server configured in `DEVPILOT_OLLAMA_ENDPOINT`. The model name comes from `DEVPILOT_MODEL`. The review screen shows that name, the comparison, progress, and a cancel button.

A finding is an AI suggestion. The screen says so. It is not a deterministic test failure, and it is not guaranteed to be correct. Quotes that were not in the diff sent to the model are dropped. Complete diffs are not stored. Prompts and model responses are not written to the log.

Install and download the model yourself before the first review. DevPilot will not pull it and will not switch to a hosted model:

```bash
brew install ollama
brew services start ollama
ollama pull qwen2.5-coder:7b
```

The default model is `qwen2.5-coder:7b`, with context `8192`, temperature `0.1`, and max output `1800`. A 20B model still requires the memory confirmation in Settings. If Ollama is stopped or the model is missing, the review fails with a local error and a retry. Details are in [docs/review-engine.md](docs/review-engine.md).

## Quality checks

Open `http://127.0.0.1:5173/quality`. DevPilot looks for PHP_CodeSniffer, PHPStan, PHPUnit, Composer, and Magento CLI files in the registered repository and suggests a command only when it finds them. Save the argument list, then confirm each run. Saving does not execute the command. A review does not execute it either.

The result shows the exact command, working directory, start time, duration, exit status, and both output streams. It is a pass, fail, skip, or timeout. It is not an AI suggestion.

Approved project scripts can still have side effects. DevPilot does not install Composer packages, edit project configuration, or run deployment commands such as `setup:upgrade` or static-content deploy. The allowlist and the manual steps are in [docs/quality-checks.md](docs/quality-checks.md).

## Release readiness

Open `http://127.0.0.1:5173/releases/new`. Choose a registered repository and a completed review. The page shows blockers, warnings, passed checks, waivers, missing evidence, the model configuration, and the Git commit identifiers. Save the report when you want a snapshot. Download that snapshot as Markdown or JSON from the report page.

The best result DevPilot can show is **Ready for human approval**. That is not approval. A waiver is listed with its reason and reviewer, and it is not a passed check. How to read the three readiness values is in [docs/release-readiness.md](docs/release-readiness.md).

## Configuration

Settings live in `.env` and, after you save the settings page, in the `app_settings` table. Environment variables are the defaults. Saved settings override the model fields on the next start.

| Variable | Default |
| --- | --- |
| `DEVPILOT_HOST` | `127.0.0.1` |
| `DEVPILOT_PORT` | `8000` |
| `DEVPILOT_FRONTEND_ORIGIN` | `http://127.0.0.1:5173` |
| `DEVPILOT_DATABASE_URL` | `sqlite:///./data/devpilot.db` |
| `DEVPILOT_LOG_LEVEL` | `INFO` |
| `DEVPILOT_LOG_DIR` | `./data/logs` |
| `DEVPILOT_OLLAMA_ENDPOINT` | `http://127.0.0.1:11434` |
| `DEVPILOT_MODEL` | `qwen2.5-coder:7b` |
| `DEVPILOT_CONTEXT_LENGTH` | `8192` |
| `DEVPILOT_TEMPERATURE` | `0.1` |
| `DEVPILOT_MAX_OUTPUT_TOKENS` | `1800` |
| `DEVPILOT_TIMEOUT_SECONDS` | `180` |
| `DEVPILOT_LARGE_MODEL_CONFIRMED` | `false` |

Keep-alive is fixed at `10m`. Concurrent inference is fixed at one request. Those two are not settings.

`DEVPILOT_OLLAMA_ENDPOINT` is accepted only when every resolved address is loopback. A path, credentials, or a hosted host name is rejected.

## Development commands

```bash
backend/.venv/bin/pytest
backend/.venv/bin/ruff check app tests
cd frontend && npm test
cd frontend && npm run build
```

Run the commands from the repository root unless the command says `cd frontend`.

## Troubleshooting

**The health check never succeeds.** Read `data/logs/devpilot.log`. Confirm port 8000 is free and `DEVPILOT_HOST` is `127.0.0.1`. Start again with `scripts/start.sh`.

**The UI says it cannot reach the backend.** Open `http://127.0.0.1:5173`, not a LAN address and not a `file://` URL. The API must already be healthy. Use Retry after `scripts/start.sh`.

**Startup says the host is not allowed.** `0.0.0.0`, a LAN address, and `*` are rejected on purpose.

**Settings reject the model or endpoint.** Use an Ollama tag such as `qwen2.5-coder:7b` and an endpoint such as `http://127.0.0.1:11434`. `gpt-4o`, `claude`, and `gemini` names are rejected. A 20B or larger tag requires the memory confirmation.

**Ollama is not running.** The Overview page shows availability as "Not checked" until you start a review. A review then shows that the local endpoint could not be reached, with a retry. Install and start Ollama locally. The app will not silently use another provider.

**A repository path is rejected.** The path must be absolute and must be the root of a Git working tree. A missing folder, a plain directory, and a `.git` file are rejected. The message stays generic and does not echo secrets.

**The model is missing.** Pull it yourself: `ollama pull qwen2.5-coder:7b`. DevPilot does not run `ollama pull`.

**A 20B model was rejected.** That is the default safety check for a 16 GB Mac. Confirm the memory requirement in Settings, or keep `qwen2.5-coder:7b`.

**SQLite will not open.** Check that `data/` is writable. The health response stays generic and does not print the filesystem path. The local log records the error type.

**Python or Node is too old.** Setup requires Python 3.11+ and Node.js 20+.

## Layout

```text
backend/app/api          HTTP routes for health, settings, and the repository explorer
backend/app/services     repository, review, model, quality, release, persistence
backend/app/models       SQLAlchemy tables
backend/app/schemas      API contracts
backend/app/db           SQLite engine and Alembic runner
backend/tests            pytest
frontend/src             React shell
docs                     architecture, API contracts, schema
scripts/setup.sh         install
scripts/start.sh         run the local UI and API
```

More detail is in [docs/architecture.md](docs/architecture.md), [docs/api-contracts.md](docs/api-contracts.md), [docs/schema.md](docs/schema.md), [docs/repository-explorer.md](docs/repository-explorer.md), [docs/review-engine.md](docs/review-engine.md), [docs/quality-checks.md](docs/quality-checks.md), and [docs/release-readiness.md](docs/release-readiness.md).
