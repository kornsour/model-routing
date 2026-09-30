---
title: Add trigger rules (all_done, one_failed, ...) to orchestra
terse: Add per-job trigger rules and a SKIPPED state to orchestra's scheduler.
repo: orchestra
allowed: ["src/orchestra/*.py", "tests/*.py", "README.md"]
category: feature
tags: [multi-module, scheduling, state-machine]
---
Pipelines keep asking for jobs that run on something other than "all my upstreams succeeded": a `send_report` that runs whether or not the loads worked, an `alert_oncall` that runs only if something failed, a `fetch_from_any_mirror` that needs just one upstream. Please add Airflow-style trigger rules to orchestra.

Read `src/orchestra/scheduler.py`'s module docstring first: it is the reference for how a run proceeds, and everything that isn't mentioned here must keep behaving exactly as it describes (the existing tests pin much of it). The data types are in `model.py`, the event-log replay in `events.py`, and `store.py` serialises results.

**What to add.** `JobSpec` gets a `trigger` field, default `"all_success"`, one of `all_success`, `all_done`, `one_failed`, `one_success`, `none_failed`; anything else is a `ValueError` at construction. It must survive `from_dict`/`to_dict`. There is a new terminal state `SKIPPED` (value `"skipped"`), recorded with a `skipped` event whose detail is the reason, like `upstream_failed`. A skipped job never ran: no attempts, no `started_at`, its `finished_at` is when it was skipped. Skipped jobs don't count toward the makespan.

**The rules.** A job with no dependencies always runs, whatever its trigger. Otherwise, while a job is `PENDING`, its rule looks at its dependencies' *current* states and decides one of: it can run now, it must keep waiting, it is `UPSTREAM_FAILED`, or it is `SKIPPED`. "Failed" below means `FAILED` or `UPSTREAM_FAILED`; "finished" means any terminal state (a job waiting to retry is not finished).

| trigger | runs when | UPSTREAM_FAILED when | SKIPPED when |
|---|---|---|---|
| `all_success` | every dependency succeeded | any dependency failed | no dependency failed and any dependency was skipped |
| `all_done` | every dependency finished | never | never |
| `one_failed` | any dependency failed | never | every dependency finished and none failed |
| `one_success` | any dependency succeeded | every dependency finished, none succeeded, and some failed | every dependency finished, none succeeded, and none failed |
| `none_failed` | every dependency finished and none failed (skipped is fine) | any dependency failed | never |

Decisions are made as early as they can be: an `all_success` job is upstream-failed the moment one dependency fails, and a `one_failed` job can start the moment one fails even if others are still running.

**Where it happens.** Step 2 of the run loop ("Propagation") becomes the place where every `PENDING` job's rule is evaluated in topological order, marking jobs `UPSTREAM_FAILED` or `SKIPPED`; because it goes in topological order, a skip or failure cascades through a chain within the same step. Step 3 dispatches the `PENDING` jobs whose rule says they can run now (plus retry-ready jobs, as today), with resources and priority applying exactly as before. Please update the docstring to describe the new behaviour.

**Reasons.** `upstream_failed` keeps today's format, `upstream <dep> <state>` naming the first failed dependency in the job's `deps` order. `SKIPPED` from `all_success` is `upstream <dep> skipped` naming the first skipped dependency; from `one_failed` it is `no upstream failed`; from `one_success` it is `no upstream succeeded`. `one_success` that ends up upstream-failed uses the `upstream <dep> <state>` form with the first failed dependency.

`replay(result.events, result.runs)` must still reproduce `result.runs` exactly, and `store.dumps`/`loads` must round-trip results that contain skipped jobs. Add tests for each rule. Keep `python -m pytest -q` green.
