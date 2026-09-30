---
title: Make orchestra's scheduler scale to 20k-job pipelines without changing its decisions
terse: Make orchestra's run loop fast on large DAGs while producing identical results.
repo: orchestra
allowed: ["src/orchestra/*.py", "tests/*.py"]
category: perf
tags: [performance, refactor, behaviour-preserving]
---
The data platform wants to simulate the full warehouse rebuild (about 20,000 jobs) before each release, and `orchestra` takes minutes on it. A profile shows why: every step of the run loop in `src/orchestra/scheduler.py` walks the whole DAG three times (completions are found by scanning, propagation scans every job, and dispatch rebuilds and re-sorts the full candidate list and re-checks every job's dependencies), and the number of steps grows with the number of jobs, so a run is quadratic.

Please make a run fast at that scale: roughly proportional to the number of jobs, dependencies and events (up to log factors), not to jobs x steps. As a yardstick, a 20,000-job layered DAG with no resource limits, 12,000 independent jobs competing for 2 slots of one resource, and a 15,000-job chain below a failing root should each take a small fraction of a second to a second or so on a laptop.

The hard constraint: **the scheduler's decisions must not change at all.** The module docstring of `scheduler.py` is the specification, and the real runner replays these decisions, so for every input the new implementation must produce exactly the same `RunResult` as the current one: the same events in the same order (including the order of events that happen at the same time: completions by name, then upstream failures in topological order, then starts in dispatch order), the same `JobRun` values, the same `runs` ordering, the same makespan. That includes the awkward cases: zero-duration attempts that complete in a later step at the same time, retries becoming ready while resources are busy, candidates that can't get resources being skipped while later ones start, jobs with no resource needs, priorities (including negative ones), duplicate entries in a job's `deps`, failure cascades through long chains, and resource pools where some kinds are exhausted and others aren't. We will diff your implementation against the current one on large randomised pipelines, so it's worth doing the same in your tests: keep a copy of the current loop as a test oracle and compare on random DAGs with resources, retries, failures and zero durations.

Keep the public API (`Scheduler(dag, capacities).run()`, `run(specs, capacities)`) and the other modules' behaviour unchanged. Keep `python -m pytest -q` green and add tests.
