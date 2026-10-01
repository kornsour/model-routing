#!/usr/bin/env bash
# Runner fleet operations: list runners and their state.
set -euo pipefail
case "${1:-list}" in
  list) echo "runner-1 online"; echo "runner-2 online" ;;
  *) echo "usage: runner-ops.sh list" >&2; exit 2 ;;
esac
