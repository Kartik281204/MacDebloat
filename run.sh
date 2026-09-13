#!/usr/bin/env bash
#
# Convenience launcher for the deblaot backend.
# Creates a local virtualenv on first run, then starts the API on
# 127.0.0.1:8765 -- localhost only, on purpose (see app/main.py).
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

./.venv/bin/pip install -q -r requirements.txt

echo "Starting deblaot on http://127.0.0.1:8765"
echo "Interactive API docs: http://127.0.0.1:8765/docs"
exec ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765
