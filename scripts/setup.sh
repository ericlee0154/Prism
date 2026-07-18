#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
".venv/bin/python" -m pip install --upgrade pip
".venv/bin/pip" install -r requirements.txt
npm install

echo "Prism is ready. Start it with: make dev"
