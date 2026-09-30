---
title: Stop wide jobs starving in orchestra (reserve dispatch and priority aging)
terse: Add a 'reserve' dispatch policy and priority aging to orchestra's scheduler.
repo: orchestra
allowed: ["src/orchestra/*.py", "tests/*.py", "README.md"]
category: feature
tags: [scheduling, fairness, spec-compliance]
---
In the warehouse pipeline, `rebuild_index` needs both warehouse slots at once. With a steady stream of one-slot jobs it never gets them, because dispatch is greedy: whenever one slot frees up, the next small job takes it. The simulation shows `rebuild_index` waiting for hours, and the real runner does the same. The other complaint is that low-priority jobs can wait forever behind a stream of newer high-priority ones. Please add two opt-in scheduling options to orchestra. The default behaviour must not change at all.

Read `src/orchestra/scheduler.py`'s module docstring first: it is the reference for how a run proceeds. Extend the docstring to describe the new options.

**API.** `Scheduler(dag, capacities=None, *, policy="greedy", aging=None)` and `orchestra.run(specs, capacities=None, *, policy="greedy", aging=None)`. `policy` is `"greedy"` (today's behaviour) or `"reserve"`; `aging` is `None` or a number > 0. Anything else is a `ValueError`.

**`policy="reserve"`.** Dispatch still walks the candidates in rank order, but a candidate that can't start *closes* every resource kind it requests for the rest of that step's dispatch. A candidate that requests any closed kind is skipped, and it closes all of its own kinds too. A candidate whose kinds are all open starts if it can acquire them; if it can't, it is skipped and closes them. Jobs that need no resources are never blocked. Kinds are reopened at the start of every step. The effect is that a blocked high-ranked job keeps lower-ranked jobs off the resources it is waiting for, while unrelated resources keep flowing.

**`aging`.** When set, candidates are ranked by *effective* priority instead of `priority`: `priority + floor(waited / aging)`, where `waited` is the time since the candidate most recently became a candidate. A `PENDING` job becomes a candidate at the step in which its dependencies are all satisfied; a job waiting to retry becomes one at its `retry_at`; the clock resets each time an attempt starts. Ties are still broken by name. Aging applies to every candidate, not just low-priority ones, so it only reorders jobs that have been waiting for different lengths of time. It works with both policies.

Everything else (completions, propagation, retries, events, `replay`) is unchanged. Add tests, including a starving wide job under greedy that runs promptly under `reserve`, and a low-priority job that overtakes a stream of later-arriving higher-priority jobs with aging. Keep `python -m pytest -q` green.
