---
title: Add critical-path planning (orchestra plan) to orchestra
terse: Add orchestra.plan.critical_path and an `orchestra plan` CLI command.
repo: orchestra
allowed: ["src/orchestra/*.py", "tests/*.py", "README.md"]
category: feature
tags: [graph-algorithms, cli, multi-module]
---
Pipeline owners want a quick answer to "which jobs decide how long my pipeline takes?" without running a full simulation. Please add critical-path planning to orchestra as a new module `src/orchestra/plan.py` and an `orchestra plan pipeline.json` CLI command next to the existing `run` (see `cli.py`; the pipeline file format is the same).

The plan assumes **unlimited resources** (capacities and priorities are ignored) but must otherwise follow the scheduler's rules exactly, including retries: `src/orchestra/scheduler.py`'s docstring and `retry.py` define them. Concretely, with no resource limits, every job that runs must get the same start (`started_at`) and finish (`finished_at`) times that `orchestra.run(specs)` would give it, and the plan's makespan must equal the run's.

**API.**
- `planned_duration(spec) -> (float, bool)`: the time from a job's first start to its terminal state, and whether it ends in success. Attempts run one after another: each takes `duration`, the outcome of attempt n is `spec.outcome(n)`, and between a failed attempt and the next one the job waits for the scheduler's back-off delay; it stops at the first `ok` or when the scheduler would not retry.
- `critical_path(specs) -> Plan`, with `Plan.jobs` (a dict of `JobPlan` in the DAG's topological order, `DAG.topo_order()`), `Plan.makespan` and `Plan.critical_path` (a list of job names).
- `JobPlan` has `name`, `reachable`, `succeeds`, `duration`, `earliest_start`, `earliest_finish`, `latest_start`, `latest_finish`, and properties `slack` (`latest_start - earliest_start`) and `critical` (slack is exactly 0).

**Semantics.** A job is *reachable* if all its dependencies are reachable and succeed. A reachable job's earliest start is the latest earliest finish among its dependencies (0 with none) and its earliest finish is that plus its planned duration; `succeeds` is whether the planned run ends in success. Unreachable jobs never run: `succeeds` is False, `duration` is 0, all four times and `slack` are `None`, and they are never critical. The makespan is the largest earliest finish (0 for an empty pipeline). Latest finish is the smallest latest start among the job's *reachable* dependents, or the makespan if it has none; latest start is latest finish minus duration. The critical path starts at the alphabetically first critical job that starts at 0 and has no critical dependency, then repeatedly follows the alphabetically first critical dependent whose earliest start equals the current job's earliest finish, until there is none.

**CLI output.** `orchestra plan FILE` prints one header line, one line per job in topological order, and a final line, then exits 0. With `W` = the length of the longest job name, or 3 if that is shorter: the header is `job` left-aligned in W characters, then two spaces, then `start`, `finish` and `slack`, each right-aligned in 6 characters and separated by two spaces, then two spaces and `note`. Each job line has the same layout: the name, then the three numbers (earliest start, earliest finish, slack) formatted with `:g` or `-` when `None`, then two spaces and a note, which is `unreachable`, `fails`, `critical` or empty, with trailing spaces stripped. The last line is `critical path: a -> b -> c (<makespan>)` (with `:g`), or `critical path: (none) (0)` for an empty pipeline.

Add tests, including a comparison against `orchestra.run` on random pipelines with retries and failures. Keep `python -m pytest -q` green and `orchestra run` unchanged.
