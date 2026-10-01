---
title: Static JSON export for the cost dashboard
terse: Add a deterministic static JSON export of ledger history, in-flight runs and pipeline critical paths, with unique slugs, pagination and manifest-based cleanup.
repo: platform
parent: platform
allowed: ["packages/orchestra/*", "packages/toolbelt/*", "packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [long-horizon, multi-package, export, determinism]
stratum: B
max_turns: 80
harvest_shape: "build-time staging/export step with an exact file layout, exclusion rules and a never-leave-it-half-done constraint (harvested #1: standalone build staging + desktop packaging)"
authorship: "Brief drafted from the shape of harvested dispatch #1 by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
The cost dashboard is moving to static hosting: no server, just JSON files in a bucket, regenerated after every nightly run. I need `ledger export` to produce them. It touches all three packages in the `platform` monorepo (current directory); `python -m pytest -q` runs every suite.

## toolbelt and orchestra pieces

1. `toolbelt.text.unique_slugs(names) -> dict[str, str]`: slug every name with `slugify`; an empty slug becomes `item`; when several names share a slug, the first in **sorted name order** keeps it and the others get `-2`, `-3`, … in that order (skipping any suffix that would itself collide with another name's plain slug). Returns `{name: slug}`.
2. `orchestra.dag.DAG.critical_path() -> tuple[list[str], float]`: let `L(job) = duration(job) + max(L(dep) for dep in deps)` (just `duration` with no deps). The path ends at the job with the largest `L` (ties: smallest name); each step back goes to the dependency with the largest `L` (ties: smallest name). Returns the job names from first to last and the path's total duration; `([], 0.0)` for an empty DAG.

## ledger.export (new module) and `ledger export`

3. `export(out_dir, history, inflight=None, specs_dir=None, page_size=50) -> list[str]` writes the files below and returns their paths relative to `out_dir`, sorted. Every JSON file is written with `json.dumps(obj, indent=2, sort_keys=True) + "\n"`. Every `total_usd` is the float sum rounded with `round(x, 2)`. Timestamps are UTC ISO strings as `ledger.store` writes them.
   - **Pipelines** are every pipeline in the history plus every pipeline with a `running` entry in `inflight.json`; slugs come from `unique_slugs`.
   - `index.json`: `{"schema_version": 1, "generated_from": {"history_records": N, "inflight_running": M}, "pipelines": {name: slug, ...}, "months": [every "YYYY-MM" with history, newest first], "run_pages": P}`.
   - `pipelines/<slug>.json`: `{"pipeline", "slug", "runs", "total_usd", "months": {"YYYY-MM": {"runs", "total_usd"}}, "last_run": <run summary or null>, "jobs": <int or null>, "critical_path": <list or null>, "critical_path_seconds": <float or null>}`. `last_run` is the run with the latest `started_at` (ties: largest `run_id`). The last three fields come from `specs_dir/<slug>.json` (a list of `JobSpec.to_dict()`s) when that file exists, else `null`.
   - `runs/page-<k>.json` for `k = 1..P`: `{"page": k, "pages": P, "page_size": page_size, "runs": [...]}`, all runs sorted by `started_at` descending then `run_id` ascending, `page_size` per page. An empty history still produces one page with no runs. A run summary is `{"run_id", "pipeline", "slug", "started_at", "status", "total_usd"}`.
   - `inflight.json`: `{"count": n, "running": [{"run_id", "pipeline", "slug", "started_at"}, ...]}` — only `running` entries, sorted by `started_at` then `run_id`.
4. **Re-exports clean up after themselves.** `export` records what it wrote in `out_dir/.export-manifest.json` (a sorted JSON list of relative paths, not itself listed). On the next export, files listed in the previous manifest that are not written this time are deleted (and directories left empty by that are removed). Files the export never wrote — a `README.md` someone dropped in the bucket folder — are never touched.
5. **Never half-done.** Read and compute everything before writing anything. If the history cannot be read (a corrupt line, say), `export` raises and `out_dir` is left exactly as it was.
6. CLI: `ledger export OUT_DIR [--history F] [--inflight F] [--specs-dir D] [--page-size N]` prints `wrote N files to OUT_DIR` (N excludes the manifest); a failure prints `export failed: <reason>` to stderr and exits 1.

## Constraints

- Stdlib only; packages talk through public names only.
- Add tests in each package's `tests/` for what you add there. Update the READMEs.
- Report back the files you changed per package and how you guarantee point 5.
