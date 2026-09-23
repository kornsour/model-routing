#!/bin/bash
# Double-click launcher: opens the dispatch routing lab like a small desktop app.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run model-routing serve --open --page dispatch
