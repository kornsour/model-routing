---
title: History migrations - engine, chain check and a renumbering
terse: Implement ledger's declarative history migrations (engine, chain checker, CLI), resolve the duplicate 0002 from two branches, and make the store upgrade old records on read.
repo: platform
parent: platform
allowed: ["packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [long-horizon, data-format, migrations, cli]
stratum: B
max_turns: 80
harvest_shape: "schema change with a migration-chain checker, collision renumbering rules and verify-before-done gates (harvested #32 and #41 migration-sequence instructions)"
authorship: "Brief drafted from the shape of harvested dispatches by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
The ledger history format is about to change three times in a month, and the first two attempts collided. `docs/ledger-migrations.md` is the agreed design for declarative migrations (read it first; it is the spec). The migration files exist, but nothing reads them yet. You are in the `platform` monorepo (current directory); `python -m pytest -q` runs every suite.

## Where things stand

- `packages/ledger/src/ledger/migrations/` has `0000_initial.json`, `0001_add_currency.json`, and **two** `0002` files from two branches that were merged on the same day: `0002_add_tags.json` merged first (an hour earlier) and `0002_status_values.json` second. Both point their `prev_id` at `0001`.
- `ledger.store` still reads and writes format version 1 only and rejects anything else. Production history files are all version 1 today; within a week they will contain version-1 lines followed by newer ones, because records are appended and never rewritten.
- Nothing checks the chain, which is how the duplicate got in.

## Do this

1. **Engine — new module `ledger.migrations`:**
   - `Migration`, a frozen dataclass with `number: int`, `name: str` (the file name), `id`, `prev_id`, `version`, `description`, `ops`.
   - `load_migrations(directory=None) -> list[Migration]` sorted by number then file name; the default directory is the package's own `migrations/`.
   - `check(migrations) -> list[str]` — every violation of the chain rules in the doc, one human-readable string each (an empty list means the chain is valid). It must catch at least: a gap or a duplicate number, `0000` not being a baseline (non-null `prev_id` or any ops), a `prev_id` that is not the previous migration's id, a `version` that is not `number + 1`, a duplicate id, and an unknown op.
   - `apply_ops(doc, ops) -> dict` — the four ops exactly as the doc defines them, returning a new dict (never mutating the input).
   - `upgrade(doc, migrations) -> dict` — brings one record to the latest version per the doc. `latest_version(migrations) -> int`.
2. **Resolve the collision** following the doc's rule: `0002_add_tags.json` keeps its number; the other becomes `0003_status_values.json` with `version` 4 and `prev_id` repointed. Do not edit its ops or description. `check(load_migrations())` must then be empty.
3. **Store:**
   - `ledger.store.load` upgrades every line to the latest version before building `RunRecord`s; a line newer than the latest version is a `ValueError`. `FORMAT_VERSION` becomes the latest version (derived from the migrations, not hard-coded).
   - `RunRecord` gains `currency: str = "USD"` and `tags: tuple[str, ...] = ()`. Its attribute stays `jobs`, but on disk the field is now `job_costs`. `to_dict` writes the latest format: `version`, `run_id`, `pipeline`, `started_at`, `status`, `total_usd`, `job_costs`, `currency`, `tags` (a list). `from_dict` accepts only the latest version; `load` is where older lines get upgraded.
   - `append` writes the latest format. Existing lines are never rewritten.
4. **CLI:**
   - `ledger migrations check [--dir D]` prints `ok (latest version N)` and exits 0, or prints each problem on its own line and exits 1.
   - `ledger migrate HISTORY --out NEW` writes an upgraded copy of a history file (every line at the latest version, same order) and refuses (exit 2, nothing written) when `NEW` already exists or is the same path as `HISTORY`.
5. Add a `tests/test_migrations.py` in the ledger package covering each op, each class of chain violation, and a mixed-version history file. Update the `ledger.store` docstring (it documents the format) and the ledger README.

## Constraints

- Stdlib only; the migration files are data, so the engine must not special-case any particular migration.
- `python -m pytest -q` at the root must be green, and so must `ledger migrations check`.

## Report back

What you built, the exact edit you made to the colliding file, and the output of `ledger migrations check`.
