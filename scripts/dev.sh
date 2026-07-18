#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x ".venv/bin/uvicorn" ]]; then
  echo "Python environment missing. Run: make setup"
  exit 1
fi

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

".venv/bin/uvicorn" apps.api.main:app --reload --host 127.0.0.1 --port 8000 &
API_PID=$!

npm run dev
