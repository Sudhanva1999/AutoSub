#!/usr/bin/env bash
# macOS double-click launcher (Finder opens .command files in Terminal).
exec "$(dirname "$0")/run_batch.sh" "$@"
