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

from collections.abc import Iterable, Mapping

from orchestra.dag import DAG
from orchestra.model import Event, JobRun, JobSpec, RunResult, State
from orchestra.pool import ResourcePool
from orchestra.retry import backoff_delay, should_retry


class Scheduler:
    def __init__(self, dag: DAG, capacities: Mapping[str, int] | None = None) -> None:
        self.dag = dag
        self.pool = ResourcePool(capacities)
        for name in dag.topo_order():
            self.pool.check(name, dag.spec(name).resources)

    def run(self) -> RunResult:
        dag = self.dag
        order = dag.topo_order()
        runs = {name: JobRun(name) for name in order}
        events: list[Event] = []
        ends: dict[str, float] = {}  # running job -> end time of its attempt
        t = 0.0
        while True:
            # 1. completions
            for name in sorted(n for n, end in ends.items() if end == t):
                del ends[name]
                spec = dag.spec(name)
                run = runs[name]
                self.pool.release(spec.resources)
                if spec.outcome(run.attempts) == "ok":
                    run.state = State.SUCCESS
                    run.finished_at = t
                    events.append(Event(t, name, "success", run.attempts))
                elif should_retry(spec, run.attempts):
                    run.state = State.RETRY_WAIT
                    run.retry_at = t + backoff_delay(spec, run.attempts)
                    events.append(Event(t, name, "retry", run.attempts, repr(run.retry_at)))
                else:
                    run.state = State.FAILED
                    run.finished_at = t
                    run.reason = f"attempt {run.attempts} failed"
                    events.append(Event(t, name, "fail", run.attempts, run.reason))
            # 2. resolution
            for name in order:
                run = runs[name]
                if run.state is not State.PENDING:
                    continue
                verdict, reason = _evaluate(dag.spec(name), runs)
                if verdict in ("upstream_failed", "skipped"):
                    run.state = State(verdict)
                    run.finished_at = t
                    run.reason = reason
                    events.append(Event(t, name, verdict, 0, reason))
            # 3. dispatch
            candidates = [
                name
                for name in order
                if (
                    runs[name].state is State.PENDING
                    and _evaluate(dag.spec(name), runs)[0] == "run"
                )
                or (
                    runs[name].state is State.RETRY_WAIT
                    and runs[name].retry_at is not None
                    and runs[name].retry_at <= t
                )
            ]
            candidates.sort(key=lambda n: (-dag.spec(n).priority, n))
            for name in candidates:
                spec = dag.spec(name)
                if not self.pool.can_acquire(spec.resources):
                    continue
                self._start(spec, runs[name], t, ends, events)
            # next step
            future = list(ends.values()) + [
                r.retry_at
                for r in runs.values()
                if r.state is State.RETRY_WAIT and r.retry_at is not None and r.retry_at > t
            ]
            if not future:
                break
            t = min(future)
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
        self, spec: JobSpec, run: JobRun, t: float, ends: dict[str, float], events: list[Event]
    ) -> None:
        self.pool.acquire(spec.resources)
        run.state = State.RUNNING
        run.attempts += 1
        run.retry_at = None
        if run.started_at is None:
            run.started_at = t
        ends[spec.name] = t + spec.duration
        events.append(Event(t, spec.name, "start", run.attempts))


_FAILED = (State.FAILED, State.UPSTREAM_FAILED)


def _evaluate(spec: JobSpec, runs: Mapping[str, JobRun]) -> tuple[str, str]:
    """Apply the job's trigger rule to its dependencies' current states:
    ``run``, ``wait``, ``upstream_failed`` or ``skipped`` (with a reason)."""
    deps = spec.deps
    if not deps:
        return "run", ""
    states = [runs[d].state for d in deps]
    failed = [d for d, s in zip(deps, states) if s in _FAILED]
    skipped = [d for d, s in zip(deps, states) if s is State.SKIPPED]
    succeeded = [d for d, s in zip(deps, states) if s is State.SUCCESS]
    done = all(s.terminal for s in states)

    def upstream(d: str) -> str:
        return f"upstream {d} {runs[d].state.value}"

    rule = spec.trigger
    if rule == "all_success":
        if failed:
            return "upstream_failed", upstream(failed[0])
        if skipped:
            return "skipped", upstream(skipped[0])
        return ("run", "") if len(succeeded) == len(deps) else ("wait", "")
    if rule == "all_done":
        return ("run", "") if done else ("wait", "")
    if rule == "one_failed":
        if failed:
            return "run", ""
        return ("skipped", "no upstream failed") if done else ("wait", "")
    if rule == "one_success":
        if succeeded:
            return "run", ""
        if not done:
            return "wait", ""
        if failed:
            return "upstream_failed", upstream(failed[0])
        return "skipped", "no upstream succeeded"
    if rule == "none_failed":
        if failed:
            return "upstream_failed", upstream(failed[0])
        return ("run", "") if done else ("wait", "")
    raise ValueError(f"unknown trigger {rule!r}")


def run(specs: Iterable[JobSpec], capacities: Mapping[str, int] | None = None) -> RunResult:
    """Build the DAG and run it."""
    return Scheduler(DAG(specs), capacities).run()
