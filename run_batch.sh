#!/usr/bin/env bash
# Generate subtitles for every video in ./input. Pass --force to reprocess everything.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "Environment not found. Run ./setup.sh first." >&2
  exit 1
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
exec .venv/bin/python -m autosub "$@"
