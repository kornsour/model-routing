#!/usr/bin/env bash
# Checks that the issues a change claims to close are referenced in docs.
set -euo pipefail
for n in "$@"; do grep -rq "#${n}" docs || { echo "issue #${n} not referenced" >&2; exit 1; }; done
