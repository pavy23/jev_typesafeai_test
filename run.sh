#!/usr/bin/env bash
# Local launcher (macOS / Linux). Creates .venv, installs deps, asks for the key once.
#
#   ./run.sh              web playground  -> http://127.0.0.1:8000 (opens browser)
#   ./run.sh demo         trial/systemone_demo.py   (add --dry-run to print the request only)
#   ./run.sh triage       samples/comment_triage    (add --fixture for offline replay)
#   ./run.sh test         offline test suite
#   ./run.sh shell        activate the venv in a subshell
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
[ -d .venv ] || { echo "· creating .venv"; "$PY" -m venv .venv; }
# a venv made by `uv venv` has no pip; bootstrap it so the same script works either way
.venv/bin/python -m pip --version >/dev/null 2>&1 || .venv/bin/python -m ensurepip --upgrade >/dev/null
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
if [ ! -f .env ]; then
  read -r -p "TYPESAFE_API_KEY (비워두면 MOCK 모드): " KEY
  echo "TYPESAFE_API_KEY=$KEY" > .env
  echo "· saved to .env (git-ignored)"
fi
cmd=${1:-web}; [ $# -gt 0 ] && shift
case "$cmd" in
  web)    echo "· http://127.0.0.1:8000  (Ctrl+C to stop)"; exec .venv/bin/python webapp/app.py --auto --open "$@" ;;
  demo)   exec .venv/bin/python trial/systemone_demo.py "$@" ;;
  triage) exec .venv/bin/python samples/comment_triage/triage.py "$@" ;;
  test)   exec .venv/bin/python -m pytest -q "$@" ;;
  shell)  exec bash --rcfile <(echo 'source .venv/bin/activate; echo "· venv active — python, pytest 사용 가능"') ;;
  *)      echo "unknown command: $cmd (web | demo | triage | test | shell)"; exit 1 ;;
esac
