#!/usr/bin/env bash
# One command for the monthly run.  First run sets up the virtualenv automatically.
#   ./run.sh                 process ./inbox and review new restaurants
#   ./run.sh --dry-run       preview only, saves nothing
#   ./run.sh --show-excluded also list what the filter dropped
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/beli-sync ]; then
  PY=$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3 || true)
  if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    echo "Need Python 3.10+.  Install with: brew install python" >&2; exit 1
  fi
  "$PY" -m venv .venv
  .venv/bin/pip install --quiet -e .
fi
[ -f .env ] || { echo "No .env yet: copy .env.example to .env and add your GOOGLE_PLACES_API_KEY." >&2; exit 1; }

exec .venv/bin/beli-sync run "$@"
