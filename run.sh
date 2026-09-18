#!/usr/bin/env bash
# One-shot local launcher (macOS / Linux): creates .venv, installs deps, asks for the key once,
# starts the playground and opens the browser. Re-run any time; it only installs what's missing.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
[ -d .venv ] || { echo "· creating .venv"; "$PY" -m venv .venv; }
# a venv made by `uv venv` has no pip; bootstrap it so the same script works either way
.venv/bin/python -m pip --version >/dev/null 2>&1 || .venv/bin/python -m ensurepip --upgrade >/dev/null
.venv/bin/python -m pip install -q -r requirements.txt
if [ ! -f .env ]; then
  read -r -p "TYPESAFE_API_KEY (비워두면 MOCK 모드): " KEY
  echo "TYPESAFE_API_KEY=$KEY" > .env
  echo "· saved to .env (git-ignored)"
fi
echo "· starting http://127.0.0.1:8000  (Ctrl+C to stop)"
exec .venv/bin/python webapp/app.py --auto --open
