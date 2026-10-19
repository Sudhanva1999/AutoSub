#!/usr/bin/env bash
# Start the AutoSub web UI and open it in your browser. Press Ctrl+C to quit.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "Environment not found. Run ./setup.sh first." >&2
  exit 1
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
exec .venv/bin/python -m autosub.web "$@"
