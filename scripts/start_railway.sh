#!/usr/bin/env sh
# Run API from repository root (Railway root directory must not be backend/).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$ROOT"
exec python -m uvicorn backend.app:app --host 0.0.0.0 --port "${PORT:-8080}"
