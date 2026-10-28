#!/usr/bin/env bash
# Start the local API and UI. Both bind to loopback.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/backend/.venv/bin/python" || ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "DevPilot is not set up. Run scripts/setup.sh first." >&2
  exit 1
fi

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

HOST="${DEVPILOT_HOST:-127.0.0.1}"
PORT="${DEVPILOT_PORT:-8000}"
UI_PORT="${DEVPILOT_UI_PORT:-5173}"

case "$HOST" in
  127.0.0.1|localhost|::1) ;;
  *)
    echo "Refusing to bind ${HOST}. DevPilot only listens on localhost." >&2
    exit 1
    ;;
esac

if [[ "$HOST" == "::1" ]]; then
  HEALTH_URL="http://[::1]:${PORT}/api/health"
else
  HEALTH_URL="http://127.0.0.1:${PORT}/api/health"
fi

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting DevPilot API on http://${HOST}:${PORT}"
(
  cd "$ROOT/backend"
  exec "$ROOT/backend/.venv/bin/python" -m app
) &
BACKEND_PID=$!

ready=0
for _ in $(seq 1 50); do
  if curl -sf "$HEALTH_URL" >/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    echo "The API process exited. Check data/logs/devpilot.log." >&2
    exit 1
  fi
  sleep 0.2
done

if [[ "$ready" -ne 1 ]]; then
  echo "The API did not become healthy at ${HEALTH_URL}. Check data/logs/devpilot.log." >&2
  exit 1
fi

echo "Starting DevPilot UI on http://127.0.0.1:${UI_PORT}"
(
  cd "$ROOT/frontend"
  export VITE_API_BASE_URL="http://127.0.0.1:${PORT}"
  exec npm run dev -- --host 127.0.0.1 --port "$UI_PORT" --strictPort
) &
FRONTEND_PID=$!

echo "DevPilot is running."
echo "  UI:  http://127.0.0.1:${UI_PORT}"
echo "  API: ${HEALTH_URL}"
echo "Press Ctrl+C to stop."

wait "$FRONTEND_PID"
