#!/usr/bin/env bash
# verify: run locally everything CI runs, before a push.
#
# Mirrors .github/workflows/ci.yml and the shared Copperline/.github ci.yml:
# Biome, tsc, Vitest, the build, the DB migration check, Semgrep, the
# migration sequence and the lockfile guard. Independent checks run in
# parallel; the build runs alone because it owns .next/. Every check prints
# its own reproduce command, and the summary names what failed.
#
# Semgrep is optional on this machine. When it is missing the check is
# SKIPPED loudly, never reported as passed: a suite that quietly covers 7 of 8
# while claiming parity is worse than one that admits the gap.
set -euo pipefail

cd "$(dirname "$0")/.."
logs="$(mktemp -d)"
trap 'rm -rf "$logs"' EXIT

declare -a names=() cmds=() pids=()
start() { # start <name> <command>: run in the background, output to a log
  names+=("$1"); cmds+=("$2")
  bash -c "$2" >"$logs/${#names[@]}.log" 2>&1 &
  pids+=("$!")
}

migration_check() {
  # Same rule as the shared workflow: schema.ts changed with no new drizzle/ file.
  local base changed
  base="$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || echo origin/main)"
  if ! git rev-parse --verify --quiet "$base" >/dev/null; then
    echo "no $base to compare against; migration check skipped"
    return 0
  fi
  changed="$(git diff --name-only "$base"...HEAD)"
  if grep -qx 'src/db/schema.ts' <<<"$changed" && ! grep -q '^drizzle/' <<<"$changed"; then
    echo "src/db/schema.ts changed but no new file under drizzle/ — run pnpm db:generate"
    return 1
  fi
  echo "migration check ok"
}
export -f migration_check

start "Lint & format (Biome)" "pnpm check"
start "Type check" "pnpm exec tsc --noEmit"
start "Unit tests (Vitest)" "pnpm test"
start "Migration sequence" "node scripts/check-migration-sequence.mjs"
start "Lockfile integrity" "scripts/check-lockfile.sh"
start "DB migration check" "migration_check"

semgrep_skipped=0
if command -v semgrep >/dev/null 2>&1; then
  start "Security scan (Semgrep)" "semgrep scan --config p/default --error"
else
  semgrep_skipped=1
fi

failed=0
summary=()
for i in "${!pids[@]}"; do
  if wait "${pids[$i]}"; then
    summary+=("  PASS  ${names[$i]}")
  else
    failed=1
    summary+=("  FAIL  ${names[$i]}    reproduce: ${cmds[$i]}")
    echo "----- ${names[$i]} (${cmds[$i]}) -----"
    cat "$logs/$((i + 1)).log"
  fi
done

# The build shares .next/ with nothing else here, but it is the slow one, so it
# runs after the fast checks have reported.
if pnpm build >"$logs/build.log" 2>&1; then
  summary+=("  PASS  Build")
else
  failed=1
  summary+=("  FAIL  Build    reproduce: pnpm build")
  echo "----- Build (pnpm build) -----"
  cat "$logs/build.log"
fi

echo
echo "pnpm verify summary:"
printf '%s\n' "${summary[@]}"
if [[ "$semgrep_skipped" == "1" ]]; then
  echo
  echo "  SKIPPED  Security scan (Semgrep): semgrep is not installed, so this run does NOT match CI."
  echo "           Install the version CI pins: pipx install semgrep==1.172.0"
fi
exit "$failed"
