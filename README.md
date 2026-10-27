# DevPilot

DevPilot is a local-first code review and release quality assistant for Magento 2 / Adobe Commerce work. The API, UI, SQLite database, and model all stay on this machine.

A review sends bounded Git diff chunks to a local Ollama model only after you start that review. Page load does not contact Ollama. If the daemon is down or the selected model is missing, the review shows the error and the setup steps. DevPilot does not download models and does not switch providers. Review findings are schema-checked. Uncertain findings are not treated as defects.

## Privacy boundaries

- Source code, Git diffs, review rows, and the SQLite file stay on this machine. A diff is sent to Ollama only when you start a review, and only to the loopback address.
- The default model is `qwen2.5-coder:7b` with an 8192-token context, temperature 0.1, and 1800 output tokens. A 20B or larger tag is refused until you confirm the extra memory use. On a 16 GB Mac, keep the 7B default.
- Model traffic goes only to a loopback Ollama URL (`http://127.0.0.1:11434` by default). The host is resolved and rejected unless every address is loopback. Hosted model names and remote endpoints are rejected. Redirects are not followed.
- The app does not load a `.env` file, and it ignores hosted-provider API keys if they are present in the environment.
- The API binds to `127.0.0.1`. The Vite dev server and preview server do the same. CORS allows only the local UI origins.
- There is no analytics, telemetry, remote logging, or error reporting.
- Git inspection is read-only. `commit`, `push`, `merge`, `reset`, `clean`, and branch switching are not in the allowlist.
- Git status runs only after you submit **Inspect repository (read-only)**. `git diff HEAD` runs only after you submit **Start review**. Startup and page load do not run Git or call Ollama.
- One review runs at a time. Cancel stops the local request. A review that exceeds the configured timeout stops with an error.
- Model output is parsed as JSON. Findings that fail the schema are discarded. Low-confidence findings, and findings whose path or lines do not match the chunk, are stored as uncertain.
- Logs do not include source code, prompts, credentials, or full model responses.
- Commands found in model output, repository files, or documentation are never executed.
- Git is invoked with an argument list (`shell` is off), a scrubbed environment, and config overrides that disable repo aliases, fsmonitor, hooks, and external diffs.
- Quality-check names are listed for later work. PHPStan and PHPCS are not executed.

## Requirements

- Python 3.9 or newer
- Node.js 20 or newer
- Git
- [Ollama](https://ollama.com) running locally when you start a review

The API still starts when Ollama is stopped. The status page shows the configured model and `not_checked` until a review starts. Install the model yourself:

```bash
ollama pull qwen2.5-coder:7b
```

## Setup

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app
```

The API listens on `http://127.0.0.1:8000`. In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Do not use a LAN address. `python -m app --host 0.0.0.0` exits with an error.

## Development commands

From the repository root, with the backend virtualenv and frontend dependencies installed:

```bash
make test
```

That runs pytest, Vitest, and the TypeScript check. You can also run them separately:

```bash
cd backend && .venv/bin/pytest
cd frontend && npm test
cd frontend && npm run typecheck
cd frontend && npm run build
```

Benchmark the configured local model against the fixture in `backend/fixtures/benchmark/cases.json`. The command prints detection rate, false-positive rate, response time, and errors. It does not download a model. If Ollama or the selected tag is missing, it exits with status 2 and does not invent rates.

```bash
cd backend && .venv/bin/python -m app.benchmark
```

Apply database migrations after pulling schema changes:

```bash
cd backend && .venv/bin/alembic upgrade head
```

## Configuration

| Variable | Default | Rule |
| --- | --- | --- |
| `DEVPILOT_HOST` | `127.0.0.1` | Must be `127.0.0.1`, `localhost`, or `::1` |
| `DEVPILOT_PORT` | `8000` | Local API port |
| `DEVPILOT_DATABASE_URL` | `sqlite:///<backend>/data/devpilot.sqlite` | Local SQLite only |
| `DEVPILOT_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Loopback `http` URL, no path. The hostname must resolve only to loopback |
| `DEVPILOT_MODEL_NAME` | `qwen2.5-coder:7b` | Local Ollama tag. Hosted names are rejected. 20B and larger need confirmation in the UI |
| `DEVPILOT_CONTEXT_LENGTH` | `8192` | 1024–8192 tokens |
| `DEVPILOT_TEMPERATURE` | `0.1` | 0–1 |
| `DEVPILOT_MAX_OUTPUT_TOKENS` | `1800` | 1–1800 tokens per chunk |
| `DEVPILOT_OLLAMA_TIMEOUT_SECONDS` | `120` | 5–300 seconds |
| `DEVPILOT_CONFIRM_LARGE_MODEL` | unset | Set to `1` to let the benchmark command use a 20B or larger tag |

## Troubleshooting

**Ollama is unavailable.** Start the local daemon with `ollama serve`, confirm `http://127.0.0.1:11434/api/tags` responds, then start the review again. DevPilot will not send the request to another provider.

**The selected model is missing.** The review shows `ollama pull <model>`. Run that command yourself. DevPilot does not pull weights.

**A 20B model was refused.** That tag is an optional experiment. Confirm the memory warning in the review form before starting. The default remains `qwen2.5-coder:7b`.

**The UI cannot reach the API.** Start `python -m app` from `backend` and reload `http://127.0.0.1:5173`.

**Local database is not ready.** From `backend`, run `alembic upgrade head`, restart `python -m app`, and retry.

**Port already in use.** Stop the other process on `8000` or `5173`, or set `DEVPILOT_PORT` and update the Vite proxy target in `frontend/vite.config.ts` to the same loopback URL.

**Git inspection was rejected.** The path must be an absolute Git working tree. Mutating Git commands are blocked even if you approve the inspection. A repository alias or fsmonitor hook is not allowed to run.

**The page does not open from another computer.** That is intentional. Both servers refuse non-loopback binds.

## Layout

- `backend/app/services/repository` — read-only Git inspection
- `backend/app/services/review` — diff chunking, schema checks, and the review engine. It depends on an inference protocol, not on a specific model client
- `backend/app/services/model` — local Ollama adapter behind that protocol
- `backend/app/benchmark` — fixture scorer for the configured local model
- `backend/app/services/quality_check` — check catalog, execution disabled
- `backend/app/services/persistence` — SQLite reviews
- `backend/app/services/release_report` — reports built only from stored rows
- `backend/app/security` — loopback checks, command approval, Git allowlist, the only `subprocess` call
- `frontend/src` — localhost UI
# DevPilot
# DevPilot
# DevPilot
