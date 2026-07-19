#!/usr/bin/env bash
# Dev launcher (macOS): starts the microservices stack (docker compose, gateway
# on :8000) + Vite frontend (:3000), opens the browser, and stops both on Ctrl+C.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running — start Docker Desktop first."
  exit 1
fi

if [ ! -f "$ROOT/.env" ]; then
  echo "Missing repo-root .env (compose secrets). Create it first:"
  echo "  cp .env.example .env   # then set APP_API_TOKEN (openssl rand -hex 16)"
  exit 1
fi

if [ ! -d "$ROOT/data/jobs/chroma" ]; then
  echo "WARNING: data/jobs/chroma missing — matching will serve 503s and the SPA"
  echo "falls back to offline estimates. Build it with:"
  echo "  backend/venv/bin/python data/scripts/build_rag.py"
fi

# Backend: the full stack (5 services + sidecars + redis + consul + gateway).
( cd "$ROOT" && docker compose up -d --build )

# Frontend (install deps once)
[ -d "$ROOT/frontend/node_modules" ] || ( cd "$ROOT/frontend" && npm install )
( cd "$ROOT/frontend" && exec npm run dev ) &
FRONT=$!

# Stop the frontend and the stack when this script is interrupted. The kill is
# best-effort (|| true): if the frontend already crashed, a failing kill under
# `set -e` would abort the trap BEFORE compose stop runs, leaking the stack.
trap 'kill "$FRONT" 2>/dev/null || true; (cd "$ROOT" && docker compose stop)' EXIT INT TERM

# Open the SPA once Vite has had a moment to boot.
( sleep 4 && open http://localhost:3000 ) &

echo "Backend  -> http://localhost:8000  (gateway; docker compose ps for services)"
echo "Frontend -> http://localhost:3000  (pid $FRONT)"
echo "Press Ctrl+C to stop both."
wait
