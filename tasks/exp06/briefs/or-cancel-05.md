---
title: Support cancelling jobs mid-run in orchestra
terse: Add external job cancellation (with cascade) to orchestra's scheduler.
repo: orchestra
allowed: ["src/orchestra/*.py", "tests/*.py", "README.md"]
category: feature
tags: [multi-module, scheduling, state-machine]
---
Operators want to simulate "what if I kill `load_orders` 20 minutes in?" before doing it for real, and the real runner needs the same semantics so it can replay the decision. Please add cancellation to orchestra.

`src/orchestra/scheduler.py`'s module docstring is the reference for how a run proceeds; extend both the code and the docstring. Anything not mentioned here must keep behaving exactly as documented (the existing tests pin a lot of it).

**API.** `Scheduler.run(cancel=None, *, cascade=True)` and `orchestra.run(specs, capacities=None, *, cancel=None, cascade=True)`. `cancel` maps job names to the time at which each is cancelled. An unknown job name or a negative time is a `ValueError` before anything runs. With no cancellations, results are identical to today's.

**New state.** `CANCELLED` (value `"cancelled"`), terminal, recorded by a `cancelled` event whose `attempt` is the job's attempt count at that moment and whose `detail` is the reason. `events.replay` and `store` must handle it, so `replay(result.events, result.runs) == result.runs` still holds for every run.

**When it happens.** Cancellation times are step times: a step happens at every cancellation time, even if nothing else happens then. Within a step, cancellations are processed after completions (so an attempt that ends at exactly the cancellation time completes normally first) and before propagation and dispatch (so a job cancelled at time t never starts at t). Several jobs cancelled at the same time are processed in name order.

**What it does.** Cancelling a job that is already in a terminal state does nothing at all: no event, no cascade. Otherwise:
- A `PENDING` job, or one waiting to retry, becomes `CANCELLED` at that time with reason `cancelled` (and no retry time).
- A `RUNNING` job's attempt is aborted: its resources are released immediately (other jobs can start in the same step), it becomes `CANCELLED`, and the reason is `cancelled while running (attempt N)`.
- With `cascade=True`, every descendant of the cancelled job that isn't terminal yet is then cancelled too, in topological order, right after it, with reason `cancelled: upstream <job>` (plus the same ` while running (attempt N)` suffix if that descendant was running).
- With `cascade=False`, descendants are left alone; the normal propagation step treats a `CANCELLED` dependency like a failed one, so they become `UPSTREAM_FAILED` with the usual `upstream <dep> cancelled` reason.

`finished_at` for a cancelled job is the cancellation time. The makespan also counts cancelled jobs that had started at least one attempt (they occupied the pipeline until they were cancelled); cancelled jobs that never started don't count.

Add tests; keep `python -m pytest -q` green.
