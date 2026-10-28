#!/usr/bin/env bash
# Install local DevPilot dependencies. Does not download a model or call Ollama.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This setup script targets macOS. The same install steps work on other Unix systems." >&2
fi

PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    PYTHON="$candidate"
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "Python 3.11 or newer is required. On macOS: brew install python@3.12" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 20 or newer is required." >&2
  exit 1
fi

node - <<'JS'
const major = Number(process.versions.node.split(".")[0]);
if (major < 20) {
  console.error("Node.js 20 or newer is required.");
  process.exit(1);
}
JS

if [[ ! -d "$ROOT/backend/.venv" ]]; then
  "$PYTHON" -m venv "$ROOT/backend/.venv"
fi

export PIP_DISABLE_PIP_VERSION_CHECK=1
"$ROOT/backend/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/backend/.venv/bin/python" -m pip install -e "$ROOT/backend[dev]"

(
  cd "$ROOT/frontend"
  npm install
)

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created .env from .env.example."
fi

mkdir -p "$ROOT/data/logs"
(
  cd "$ROOT/backend"
  "$ROOT/backend/.venv/bin/python" - <<'PY'
from app.config import get_settings
from app.db.migrate import init_database

init_database(get_settings().database_url)
print("SQLite database is ready.")
PY
)

cat <<'EOF'

DevPilot is set up. The database and logs are under ./data and stay on this machine.

Start the app:
  scripts/start.sh

Ollama was not contacted, and no model was downloaded.
Before a later review phase, install Ollama and pull the default model yourself:

  brew install ollama
  brew services start ollama
  ollama pull qwen2.5-coder:7b

The default model is qwen2.5-coder:7b for a 16 GB Apple silicon Mac.
A 20B model is an optional experiment only after you confirm the extra memory use.

EOF
