# DevPilot

DevPilot is a local-first code review and release-quality assistant for a Magento 2 / Adobe Commerce agency. Phase 0 is the application shell: a loopback API, a loopback UI, SQLite, and local model settings. It does not run reviews yet.

Source code, git diffs, findings, and the database stay on this machine. Inference is reserved for a locally running Ollama model. There is no hosted-model fallback.

## Privacy boundaries

- The API binds to loopback (`127.0.0.1` by default). It refuses `0.0.0.0` and other public hosts.
- The UI dev server binds to `127.0.0.1`. Open `http://127.0.0.1:5173`.
- CORS allows only the local UI origin.
- The only model provider is Ollama. The endpoint must resolve to a loopback address.
- Hosted model names are rejected. `qwen2.5-coder:7b` is the default on a 16 GB Apple silicon Mac.
- A model at 20B parameters or larger is an optional experiment. Set `large_model_confirmed=true` only after accepting the extra memory use.
- The app does not call Ollama until a review starts. Phase 0 never starts a review, so it never calls Ollama.
- The app does not download models. If the selected model is missing, pull it yourself.
- Git inspection is read-only. The app does not commit, push, merge, reset, clean, or switch branches, and Phase 0 does not run git at all.
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

**Ollama is not running.** Phase 0 does not call it. The Overview page shows availability as "Not checked". When a later phase starts a review, a connection error is shown with a retry. Install and start Ollama locally. The app will not silently use another provider.

**The model is missing.** Pull it yourself: `ollama pull qwen2.5-coder:7b`. DevPilot does not run `ollama pull`.

**A 20B model was rejected.** That is the default safety check for a 16 GB Mac. Confirm the memory requirement in Settings, or keep `qwen2.5-coder:7b`.

**SQLite will not open.** Check that `data/` is writable. The health response stays generic and does not print the filesystem path. The local log records the error type.

**Python or Node is too old.** Setup requires Python 3.11+ and Node.js 20+.

## Layout

```text
backend/app/api          HTTP routes mounted in Phase 0
backend/app/services     repository, review, model, quality, release, persistence
backend/app/models       SQLAlchemy tables
backend/app/schemas      API contracts, including routes not mounted yet
backend/app/db           SQLite engine and Alembic runner
backend/tests            pytest
frontend/src             React shell
docs                     architecture, API contracts, schema
scripts/setup.sh         install
scripts/start.sh         run the local UI and API
```

More detail is in [docs/architecture.md](docs/architecture.md), [docs/api-contracts.md](docs/api-contracts.md), and [docs/schema.md](docs/schema.md).
