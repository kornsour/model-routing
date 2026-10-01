---
title: Ledger in-flight runs - shutdown pause and heartbeat liveness
terse: Replace ledger's age-based stale-run reaping with heartbeat liveness shared by the reaper and the overlap guard, and pause tracked runs on shutdown.
repo: platform
parent: platform
allowed: ["packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [long-horizon, liveness, signals, multi-module]
stratum: B
max_turns: 80
harvest_shape: "two related fixes with prior investigation, numbered tasks and required tests (harvested #25: shutdown hook + run heartbeat)"
authorship: "Brief drafted from the shape of harvested dispatch #25 by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
You are implementing two related fixes to `ledger.inflight` in the `platform` monorepo (current directory). Read `packages/ledger/src/ledger/inflight.py` and its tests first; the module docstring explains why the stale threshold is as generous as it is.

## The problem (already investigated — do not re-investigate, build on this)

Pipeline runs get stuck in `inflight.json` with status `running` for up to six hours when the runner process dies. From the last month's `inflight.json` snapshots: four runs were reaped as abandoned, two of them `hourly` runs, and `hourly` never runs longer than nine minutes, so those can only be process death. Worse, `already_running()` treats the dead row as live, so every `hourly` run scheduled in those six hours was skipped: the scheduler thought one was already going.

Two root causes, both yours:

1. **Nothing runs on shutdown.** When the runner gets SIGTERM (deploys, host maintenance), it exits without touching `inflight.json`.
2. **`started_at` is the only liveness signal.** `reap_stale` compares run age against a flat `STALE_AFTER` (6 h). A run that died five minutes in is indistinguishable from a legitimate 4.5-hour nightly run.

## Task A — heartbeat, so liveness is measured, not guessed

1. Every entry gets a `heartbeat_at` (ISO, UTC). `start()` sets it equal to `started_at`.
2. Add `heartbeat(path, run_id, now)`: refreshes `heartbeat_at` of a `running` entry; does nothing to an entry in any other status; an unknown `run_id` is a `KeyError`.
3. Add `report_progress(path, run_id, done, total, now)`: records `progress = {"done": done, "total": total}` **and** refreshes `heartbeat_at` in the same write. The runner already calls a progress hook per finished job; progress is the cheapest heartbeat there is.
4. Add `HEARTBEAT_STALE = timedelta(minutes=15)` and `ATTEMPT_TIMEOUT = timedelta(minutes=10)` (the longest a single job attempt may run before the runner kills it; progress can be silent that long). Keep `STALE_AFTER` exported and unchanged.
5. Factor liveness into **one exported helper**, `is_live(entry, now) -> bool`, used by both `reap_stale` and `already_running`, so the reaper and the overlap guard can never disagree about what "live" means:
   - only a `running` entry can be live;
   - if it has a `heartbeat_at`, it is live while `now - heartbeat_at <= HEARTBEAT_STALE`;
   - if it has no `heartbeat_at` (rows written before this change — the key is absent or `null`), fall back to the old rule: live while `now - started_at <= STALE_AFTER`. This branch is not optional; old rows exist in production files.
6. `reap_stale(path, now)` marks every `running` entry that is not live as `abandoned`, keeps returning the sorted list of reaped ids, and records **why** in a new field `reaped_by`: `"heartbeat"` when the row had a heartbeat and went silent, `"age"` when it fell back to the age rule. Keep the existing reason wording's promise ("Nothing it finished was lost.") in both reasons, and make the two reasons distinguishable.
7. `already_running(path, pipeline)` gains a `now` parameter and is true only if some entry for that pipeline `is_live`. A dead row that has not been reaped yet must no longer block the pipeline.

## Task B — shutdown pause

1. A module-level registry of the run ids this process is running: `track(run_id)` and `untrack(run_id)`, plus `ACTIVE` (a `set`) for inspection.
2. `install_shutdown_handlers(path, clock=None)` registers handlers for SIGTERM and SIGINT **at most once per process** (a module-level `SHUTDOWN_INSTALLED` flag; a second call only updates the stored `path`/`clock`). `clock` is a zero-argument callable returning an aware UTC `datetime`; default `datetime.now(UTC)`.
3. `handle_shutdown(signum) -> list[str]` does the work and is what the installed handler calls: every tracked run whose entry is still `running` becomes `paused`, with `paused_at` set and a `reason` naming the signal by name, e.g. `"Paused: the process running this exited (SIGTERM). Everything it finished is saved; resume it to carry on."` Entries in any other status are left exactly as they are; returns the sorted paused ids. The installed handler then restores the default handler and re-raises the signal so the process still exits with the conventional status.
4. `resume(path, run_id, now)`: `paused` → `running`, with a fresh `heartbeat_at`; resuming anything not `paused` is a `ValueError`. `paused` is not `abandoned`: it means "coming back to this", and neither the reaper nor the overlap guard may treat a paused run as live or reap it.

## CLI and docs

- `ledger reap` accepts `--now ISO` (default: the current time) and prints `reaped <run_id> (<reaped_by>)` per reaped run.
- Rewrite the `ledger.inflight` docstring to describe heartbeat liveness, the fallback, and pause/resume; update the ledger README row.

## Tests

Extend `packages/ledger/tests/test_inflight.py` rather than inventing a new pattern. Cover at minimum: a run with a fresh heartbeat is **not** reaped even when `started_at` is older than `STALE_AFTER` (this is the whole point — it un-breaks the 4.5-hour nightly run); a run silent past `HEARTBEAT_STALE` is reaped; a row with no `heartbeat_at` still falls back to the age rule; `paused` and terminal entries are never touched by either path; the shutdown handler pauses `running` tracked rows and leaves terminal rows alone; and `HEARTBEAT_STALE > ATTEMPT_TIMEOUT` — assert the relationship so a future timeout bump cannot silently start reaping live runs.

`python -m pytest -q` at the root must stay green. Stdlib only.

Report back: what you changed in each file, how the installed handler re-raises, and anything you deliberately did not do.
