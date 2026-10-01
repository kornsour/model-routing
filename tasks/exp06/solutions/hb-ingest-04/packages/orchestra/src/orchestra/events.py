"""Rebuilding job states from an event log.

The real runner persists only the event log; the dashboard rebuilds job
states from it with ``replay``.  ``replay(result.events, names)`` must give
the same ``JobRun`` values as ``result.runs`` for every run.

On disk a run's log is a series of segments ``events-1.jsonl``,
``events-2.jsonl``, ... (one ``Event.to_dict()`` per line; the runner rolls
to a new segment every 10,000 events). ``read_log`` reads them in segment
number order and tolerates a truncated final line in the last segment (the
runner was killed mid-write); ``result_from_log`` rebuilds a ``RunResult``
from the events and the job specs.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from orchestra.model import Event, JobRun, JobSpec, RunResult, State

KINDS = ("start", "success", "retry", "fail", "upstream_failed")
_SEGMENT = re.compile(r"events-(\d+)\.jsonl$")


def replay(events: Iterable[Event], names: Iterable[str]) -> dict[str, JobRun]:
    runs = {name: JobRun(name) for name in names}
    for ev in events:
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


def _segment_number(path: Path) -> int:
    m = _SEGMENT.search(path.name)
    if not m:
        raise ValueError(f"{path}: not an event-log segment (events-N.jsonl)")
    return int(m.group(1))


def read_log(paths: Iterable[str | Path]) -> list[Event]:
    """Read event-log segments in segment-number order."""
    segments = sorted((Path(p) for p in paths), key=_segment_number)
    events: list[Event] = []
    for index, path in enumerate(segments):
        lines = path.read_text().split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        for lineno, line in enumerate(lines, start=1):
            last_line = index == len(segments) - 1 and lineno == len(lines)
            try:
                doc = json.loads(line)
                event = Event(**doc)
            except (json.JSONDecodeError, TypeError) as exc:
                if last_line:
                    break
                raise ValueError(f"{path.name}:{lineno}: malformed event: {exc}") from exc
            if event.kind not in KINDS:
                raise ValueError(f"{path.name}:{lineno}: unknown event kind {event.kind!r}")
            if events and event.time < events[-1].time:
                raise ValueError(f"{path.name}:{lineno}: event time goes backwards")
            events.append(event)
    return events


def result_from_log(events: list[Event], specs: Iterable[JobSpec]) -> RunResult:
    """A ``RunResult`` rebuilt from a (possibly partial) event log."""
    names = [s.name for s in specs]
    runs = replay(events, names)
    makespan = max(
        (
            r.finished_at
            for r in runs.values()
            if r.state in (State.SUCCESS, State.FAILED) and r.finished_at is not None
        ),
        default=0.0,
    )
    return RunResult(runs=runs, events=list(events), makespan=makespan)
