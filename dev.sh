#!/usr/bin/env bash
# Dev launcher (macOS): runs the FastAPI backend (:8000) + Vite frontend (:3000),
# opens the browser, and stops both on Ctrl+C.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -x "$ROOT/backend/venv/bin/python" ]; then
  echo "Missing backend venv. Create it first:"
  echo "  cd backend && python3 -m venv venv && venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

# Backend
( cd "$ROOT/backend" && exec venv/bin/python -m uvicorn app.main:app --port 8000 ) &
BACK=$!

# Frontend (install deps once)
[ -d "$ROOT/frontend/node_modules" ] || ( cd "$ROOT/frontend" && npm install )
( cd "$ROOT/frontend" && exec npm run dev ) &
FRONT=$!

# Stop both when this script is interrupted.
trap 'kill "$BACK" "$FRONT" 2>/dev/null' EXIT INT TERM

# Open the SPA once Vite has had a moment to boot.
( sleep 4 && open http://localhost:3000 ) &

echo "Backend  -> http://localhost:8000  (pid $BACK)"
echo "Frontend -> http://localhost:3000  (pid $FRONT)"
echo "Press Ctrl+C to stop both."
wait
