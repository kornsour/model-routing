"""The discrete-event run loop.

This docstring is the reference for how a run proceeds.

A run starts at time 0 with every job ``PENDING`` and proceeds in *steps*.
Each step happens at a time ``t`` and does, in order:

1. **Completions.** Every running attempt that ends at ``t`` completes, in
   job-name order, and releases its resources.  An ``ok`` attempt makes the
   job ``SUCCESS`` (event ``success``).  A ``fail`` attempt either schedules a
   retry - the job becomes ``RETRY_WAIT`` with ``retry_at = t + delay``
   (``orchestra.retry.backoff_delay``) and a ``retry`` event whose detail is
   the retry time - or, when the job has used ``max_attempts``, makes it
   ``FAILED`` (event ``fail``).
2. **Propagation.** In topological order, a ``PENDING`` job with a
   dependency that is ``FAILED`` or ``UPSTREAM_FAILED`` becomes
   ``UPSTREAM_FAILED`` (event ``upstream_failed``); the reason names the
   first such dependency in the job's ``deps`` order.
3. **Dispatch.** The candidates are the ``PENDING`` jobs whose dependencies
   are all ``SUCCESS`` plus the ``RETRY_WAIT`` jobs with ``retry_at <= t``.
   They are considered by descending ``priority``, then name.  Each one that
   can acquire all of its resources right now starts (event ``start``): it
   becomes ``RUNNING``, its attempt counter goes up by one, and the attempt
   ends at ``t + duration``.  A candidate that cannot acquire its resources is
   skipped for this step; candidates after it may still start.

The next step is at the earliest time among the running attempts' end times
and the ``retry_at`` times still in the future.  When there is none, the run
is over.  (A zero-duration attempt ends at the same ``t``; the next step then
happens at the same time.)

``started_at`` is the start of a job's first attempt, ``finished_at`` the time
it reached a terminal state, and the run's ``makespan`` is the latest
``finished_at`` of a job that ran (``SUCCESS`` or ``FAILED``), or 0.
"""

from __future__ import annotations

import bisect
import heapq
from collections.abc import Iterable, Mapping

from orchestra.dag import DAG
from orchestra.model import Event, JobRun, JobSpec, RunResult, State
from orchestra.pool import ResourcePool
from orchestra.retry import backoff_delay, should_retry


class Scheduler:
    """Event-driven implementation of the loop described above.

    Work per step is proportional to what changes in that step (completions,
    newly ready jobs, jobs that can start), not to the size of the DAG.
    """

    def __init__(self, dag: DAG, capacities: Mapping[str, int] | None = None) -> None:
        self.dag = dag
        self.pool = ResourcePool(capacities)
        for name in dag.topo_order():
            self.pool.check(name, dag.spec(name).resources)

    def run(self) -> RunResult:
        dag = self.dag
        pool = self.pool
        order = dag.topo_order()
        topo_index = {n: i for i, n in enumerate(order)}
        specs = {n: dag.spec(n) for n in order}
        uniq_deps = {n: tuple(dict.fromkeys(specs[n].deps)) for n in order}
        dependents: dict[str, list[str]] = {n: [] for n in order}
        for n in order:
            for d in uniq_deps[n]:
                dependents[d].append(n)
        remaining = {n: len(uniq_deps[n]) for n in order}
        runs = {name: JobRun(name) for name in order}
        events: list[Event] = []
        # Ready candidates sorted by (-priority, name), split by whether they
        # need resources: resource-free ones always start in the step they are
        # ready, so only ``ready_res`` carries over between steps.
        ready_free: list[tuple[int, str]] = []
        ready_res: list[tuple[int, str]] = []
        ends: list[tuple[float, str]] = []  # heap of running attempts
        retries: list[tuple[float, str]] = []  # heap of retry times

        def make_ready(name: str) -> None:
            key = (-specs[name].priority, name)
            bisect.insort(ready_res if specs[name].resources else ready_free, key)

        for n in order:
            if remaining[n] == 0:
                make_ready(n)

        t = 0.0
        while True:
            # 1. completions
            newly_failed: list[str] = []
            while ends and ends[0][0] == t:
                _, name = heapq.heappop(ends)
                spec = specs[name]
                run = runs[name]
                pool.release(spec.resources)
                if spec.outcome(run.attempts) == "ok":
                    run.state = State.SUCCESS
                    run.finished_at = t
                    events.append(Event(t, name, "success", run.attempts))
                    for m in dependents[name]:
                        remaining[m] -= 1
                        if remaining[m] == 0 and runs[m].state is State.PENDING:
                            make_ready(m)
                elif should_retry(spec, run.attempts):
                    run.state = State.RETRY_WAIT
                    run.retry_at = t + backoff_delay(spec, run.attempts)
                    events.append(Event(t, name, "retry", run.attempts, repr(run.retry_at)))
                    heapq.heappush(retries, (run.retry_at, name))
                else:
                    run.state = State.FAILED
                    run.finished_at = t
                    run.reason = f"attempt {run.attempts} failed"
                    events.append(Event(t, name, "fail", run.attempts, run.reason))
                    newly_failed.append(name)
            # 2. propagation
            if newly_failed:
                affected: set[str] = set()
                stack = list(newly_failed)
                while stack:
                    n = stack.pop()
                    for m in dependents[n]:
                        if m not in affected and runs[m].state is State.PENDING:
                            affected.add(m)
                            stack.append(m)
                for name in sorted(affected, key=topo_index.__getitem__):
                    run = runs[name]
                    bad = next(
                        d
                        for d in specs[name].deps
                        if runs[d].state in (State.FAILED, State.UPSTREAM_FAILED)
                    )
                    run.state = State.UPSTREAM_FAILED
                    run.finished_at = t
                    run.reason = f"upstream {bad} {runs[bad].state.value}"
                    events.append(Event(t, name, "upstream_failed", 0, run.reason))
            # 3. dispatch
            while retries and retries[0][0] <= t:
                _, name = heapq.heappop(retries)
                make_ready(name)
            if ready_free or ready_res:
                kept: list[tuple[int, str]] = []
                i = j = 0
                exhausted = False
                while i < len(ready_free) or (j < len(ready_res) and not exhausted):
                    take_free = j >= len(ready_res) or exhausted or (
                        i < len(ready_free) and ready_free[i] < ready_res[j]
                    )
                    if take_free:
                        name = ready_free[i][1]
                        i += 1
                        self._start(specs[name], runs[name], t, ends, events)
                        continue
                    item = ready_res[j]
                    j += 1
                    spec = specs[item[1]]
                    if not pool.can_acquire(spec.resources):
                        kept.append(item)
                        continue
                    self._start(spec, runs[item[1]], t, ends, events)
                    if all(pool.available(r) == 0 for r in pool.capacities):
                        exhausted = True
                kept.extend(ready_res[j:])
                ready_free = []
                ready_res = kept
            # next step
            nxt = [ends[0][0]] if ends else []
            if retries:
                nxt.append(retries[0][0])
            if not nxt:
                break
            t = min(nxt)
        makespan = max(
            (
                r.finished_at
                for r in runs.values()
                if r.state in (State.SUCCESS, State.FAILED) and r.finished_at is not None
            ),
            default=0.0,
        )
        return RunResult(runs=runs, events=events, makespan=makespan)

    def _start(
        self,
        spec: JobSpec,
        run: JobRun,
        t: float,
        ends: list[tuple[float, str]],
        events: list[Event],
    ) -> None:
        self.pool.acquire(spec.resources)
        run.state = State.RUNNING
        run.attempts += 1
        run.retry_at = None
        if run.started_at is None:
            run.started_at = t
        heapq.heappush(ends, (t + spec.duration, spec.name))
        events.append(Event(t, spec.name, "start", run.attempts))


def run(specs: Iterable[JobSpec], capacities: Mapping[str, int] | None = None) -> RunResult:
    """Build the DAG and run it."""
    return Scheduler(DAG(specs), capacities).run()
