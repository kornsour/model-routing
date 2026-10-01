---
title: Price real runs from the runner's event logs
terse: Teach orchestra to read the runner's segmented event logs and rebuild a RunResult, and teach ledger to ingest and price real runs idempotently.
repo: platform
parent: platform
allowed: ["packages/orchestra/*", "packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [long-horizon, multi-package, ingestion, idempotency]
stratum: B
max_turns: 80
harvest_shape: "feature spanning two components with read-first list, prior findings and a precise contract (harvested #43: four ATS adapters matching existing fetchers' shape)"
authorship: "Brief drafted from the shape of harvested implementation dispatches by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
The ledger only prices *simulated* runs today: `ledger price`/`record` read an `orchestra.store` result file, which only the simulator writes. The real runner persists nothing but its event log, so no production run has ever been priced. This change closes that gap across `orchestra` and `ledger` in the `platform` monorepo (current directory).

## Read first

- `packages/orchestra/src/orchestra/events.py` — `replay` already rebuilds job states from events, and its docstring says why the dashboard depends on it.
- `packages/orchestra/src/orchestra/scheduler.py` — the module docstring defines `makespan`.
- `packages/ledger/src/ledger/pricing.py`, `store.py`, `cli.py`.

## What the runner writes (verified on the runner host)

One directory per run under a runs root, named by run id:

```
runs/<run_id>/meta.json          {"run_id", "pipeline", "started_at": ISO, "specs": [JobSpec.to_dict(), ...]}
runs/<run_id>/events-1.jsonl     one Event.to_dict() per line
runs/<run_id>/events-2.jsonl     ...the runner rolls to a new segment every 10,000 events
```

Two things bit the first prototype: segments sort lexically wrong once there are ten of them (`events-10` before `events-2`), and when the runner is killed mid-write the **last** segment can end in a truncated line with no newline. A run that is still going simply has fewer events than it will have later.

## Required behaviour

**orchestra**

1. `orchestra.events.read_log(paths) -> list[Event]`: reads the given segment files in segment-number order (the integer `N` in `events-N.jsonl`, regardless of the order passed). A truncated or unparseable **final line of the last segment** is ignored. Any other malformed line is a `ValueError` whose message names the file and the 1-based line number. An unknown event `kind`, or an event whose `time` is earlier than the previous event's, is also a `ValueError`.
2. `orchestra.events.result_from_log(events, specs) -> RunResult`: `runs` from `replay` over every spec name (jobs with no events stay `PENDING`), `events` as given, and `makespan` exactly as the scheduler defines it. For a complete log of a simulated run, the result must equal what the simulator returned (same `runs`, same `makespan`).
3. Export both from `orchestra.events`, and document the segment format in its module docstring.

**ledger**

4. `ledger.pricing.price_run` gains a keyword-only `open_until: float | None = None`. When given, an attempt that started but has no ending event is billed from its start to `open_until` ("billed so far"); when `None` (the default) such attempts are not billed, as today.
5. New module `ledger.ingest`:
   - `ingest_run(run_dir, rates) -> Ingested` (a frozen dataclass: `record: RunRecord`, `complete: bool`, `finished: int`, `total: int`). It reads `meta.json` and every `events-*.jsonl`, rebuilds the result, and prices it with `open_until` set to the time of the last event (0 for an empty log). `complete` means every job is terminal; `finished`/`total` count terminal jobs and all jobs. The record's `status` is `"success"` when complete and every job succeeded, `"failed"` when complete otherwise, and `"incomplete"` when not complete. `run_id`, `pipeline` and `started_at` come from `meta.json`.
   - `ingest_all(runs_root, history_path, rates) -> tuple[list[str], list[str]]` — `(appended, incomplete)`, both sorted. Every run directory whose run id is not already in the history is ingested; complete runs are appended to the history, incomplete ones are only reported. Running it again, or after more segments arrive, must append each run **exactly once**, and never the incomplete version.
6. CLI: `ledger ingest RUNS_ROOT [--history F] [--rates R]` prints `ingested <run_id>` for each appended run and `incomplete <run_id> (<finished> of <total> jobs finished)` for each incomplete one, in run-id order, ingested lines first. Exit status 0.

## Constraints

- Stdlib only. `ledger` must not import any `_`-prefixed name from `orchestra`; if it needs something, make it public there.
- Keep `replay`'s behaviour exactly as documented; the dashboard depends on it.
- Add tests in each package's own `tests/` directory for what you add there, following the existing style. `python -m pytest -q` at the root stays green.
- Update the ledger README (module table) and the `orchestra.events` docstring.

## Report back

What you added in each package, how segment ordering and truncation are handled, and how idempotency is guaranteed.
