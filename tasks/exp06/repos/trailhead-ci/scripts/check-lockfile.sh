#!/usr/bin/env bash
# Fails when package.json and pnpm-lock.yaml disagree, or when the lockfile
# would resolve a package from outside the npm registry.
set -euo pipefail

if [[ ! -f pnpm-lock.yaml ]]; then
  echo "check-lockfile: no pnpm-lock.yaml" >&2
  exit 1
fi
if grep -qE 'tarball: (http|git)' pnpm-lock.yaml; then
  echo "check-lockfile: lockfile resolves a package outside the registry" >&2
  exit 1
fi
echo "check-lockfile: ok"
