#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .venv/bin/python ]; then
  python3.12 -m venv .venv
  .venv/bin/python -m pip install -r requirements.lock
  .venv/bin/python -m pip install --no-deps -e .
fi
if [ ! -d frontend/node_modules ]; then
  npm --prefix frontend ci
fi
.venv/bin/python -m backend.app.cli build
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
LAB_API_PID=$!
trap 'kill "$LAB_API_PID" 2>/dev/null || true' EXIT
npm --prefix frontend run dev -- --port 5173
