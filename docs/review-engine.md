# Review engine

Phase 2 sends a selected diff to the Ollama server on this machine. It does not download a model, search the web, or call a hosted API. A finding is an AI suggestion. It is not a deterministic test failure, and it is not guaranteed to be correct.

## Configure the model

The model name has to be set. The default is `qwen2.5-coder:7b`. Change it in `.env` or in Settings. The endpoint has to be an Ollama origin on loopback, with an explicit port. The default is `http://127.0.0.1:11434`.

```bash
DEVPILOT_OLLAMA_ENDPOINT=http://127.0.0.1:11434
DEVPILOT_MODEL=qwen2.5-coder:7b
DEVPILOT_CONTEXT_LENGTH=8192
DEVPILOT_TEMPERATURE=0.1
DEVPILOT_MAX_OUTPUT_TOKENS=1800
DEVPILOT_TIMEOUT_SECONDS=180
```

Keep-alive stays `10m`. Only one review request talks to Ollama at a time. A model at 20B parameters or larger is rejected until `DEVPILOT_LARGE_MODEL_CONFIRMED=true`.

DevPilot checks the endpoint again when a review starts. A name that does not resolve to loopback, a path, or a hosted host is rejected. There is no fallback provider.

## Download the model yourself

DevPilot does not run `ollama pull` and does not call Ollama while it is idle. Install Ollama and download the configured tag in a separate step:

```bash
brew install ollama
brew services start ollama
ollama pull qwen2.5-coder:7b
```

Use the same tag you configured. If the tag is missing, the review fails with `model_missing` and tells you to pull it. If Ollama is stopped, the review fails with `unavailable`. A slow response fails with `timeout`. Retry after fixing the local service. The app will not switch models or providers on its own.

## What a review does

1. You choose a registered repository, a base branch, and changed files.
2. DevPilot stores a manifest: repository id, base, current HEAD, selected paths, and the local model settings. It does not store the complete diff.
3. It skips credential-shaped paths, binaries, generated directories, `*.min.js`, `*.min.css`, `*.map`, `package-lock.json`, and globs listed in `.devpilotignore`. A diff that looks like a private key is skipped and is not sent to the model.
4. Large diffs are split into chunks that keep the file path, the scope, and the line numbers. A few preceding lines are repeated when they fit.
5. Each chunk goes to `POST /api/chat` on the configured origin. The request uses JSON format, the configured temperature, context, and max output. It does not enable tools.
6. The response must match a strict schema. A quote or a line number that was not in that chunk becomes a limitation, not a finding.
7. Overlapping comments for the same file, scope, and category keep the higher severity.
8. The summary and findings are stored in SQLite. `validation_status` stays `uncertain`.

The categories are functional defects, security, Magento dependency injection, service contracts, store scope, SQL, cache and indexers, validation and escaping, performance and maintainability, and missing tests.

## How to run one

Start DevPilot with `scripts/start.sh`. Open `http://127.0.0.1:5173/reviews/new`, or save a file selection on a repository and follow **Review the saved selection**.

The review page shows the model name, the comparison, files reviewed, files skipped, limitations, and progress. Cancel stops the review between chunks. History is the Reviews list.

## Tests

```bash
backend/.venv/bin/pytest backend/tests/test_review_engine.py
cd frontend && npm test
```

The backend tests mock Ollama. They cover malformed JSON, a missing model, a timeout, an empty diff, an oversized diff, duplicate findings, and a secret-shaped diff that is not sent. They do not contact port 11434.
