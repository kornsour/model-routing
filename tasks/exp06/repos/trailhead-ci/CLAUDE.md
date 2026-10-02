# CLAUDE.md — Pathwise

Pathwise is a single-operator career app (Next.js, Drizzle, Postgres).

## Code Style

- Biome only: `pnpm check:fix`, then `pnpm check`. `pnpm check` is Biome only;
  it is not a type check. Run `pnpm exec tsc --noEmit` separately.
- Shell scripts are bash with `set -euo pipefail`, commented for the next
  person who reads them at 7am.

## Testing

- `pnpm test` runs Vitest. The e2e suite (`pnpm e2e`) is local-only forever
  (ADR-0023) and runs from `scripts/hooks/pre-push`.
- Migrations: never hand-edit `drizzle/`; `node scripts/check-migration-sequence.mjs`
  validates numbering and the snapshot chain.
