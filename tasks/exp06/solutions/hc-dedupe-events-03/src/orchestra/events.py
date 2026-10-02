"""Rebuilding job states from an event log.

The real runner persists only the event log; the dashboard rebuilds job
states from it with ``replay``.  ``replay(result.events, names)`` must give
the same ``JobRun`` values as ``result.runs`` for every run.

Delivery from the runner is at-least-once (``docs/runner-protocol.md``): an
event is identified by ``(job, kind, attempt)`` and the first copy received
is authoritative, so ``replay`` first drops later copies with ``dedupe``.
"""

from __future__ import annotations

from collections.abc import Iterable

from orchestra.model import Event, JobRun, State


def dedupe(events: Iterable[Event]) -> list[Event]:
    """Keep the first copy of each ``(job, kind, attempt)``, in order."""
    seen: set[tuple[str, str, int]] = set()
    out: list[Event] = []
    for ev in events:
        key = (ev.job, ev.kind, ev.attempt)
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out


def replay(events: Iterable[Event], names: Iterable[str]) -> dict[str, JobRun]:
    runs = {name: JobRun(name) for name in names}
    for ev in dedupe(events):
        run = runs[ev.job]
        if ev.kind == "start":
            run.state = State.RUNNING
            run.attempts = ev.attempt
            run.retry_at = None
            if run.started_at is None:
                run.started_at = ev.time
        elif ev.kind == "success":
            run.state = State.SUCCESS
            run.finished_at = ev.time
        elif ev.kind == "retry":
            run.state = State.RETRY_WAIT
            run.retry_at = float(ev.detail)
        elif ev.kind == "fail":
            run.state = State.FAILED
            run.finished_at = ev.time
            run.reason = ev.detail
        elif ev.kind == "upstream_failed":
            run.state = State.UPSTREAM_FAILED
            run.finished_at = ev.time
            run.reason = ev.detail
        else:
            raise ValueError(f"unknown event kind {ev.kind!r}")
    return runs
