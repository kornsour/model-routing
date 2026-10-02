"""Hidden grader: tolerant replay (exp06 stratum C; keyed interpretation)."""

from orchestra import JobSpec, run
from orchestra.events import dedupe, replay
from orchestra.model import Event


def _run():
    specs = [JobSpec("load_orders", duration=2, outcomes=("fail", "ok"), max_attempts=2, backoff=1),
             JobSpec("report", deps=("load_orders",), duration=1), JobSpec("side", duration=5)]
    return run(specs)


def test_resent_copies_dropped_first_wins():
    res = _run()
    ev = res.events
    resent = []
    for e in ev:
        resent.append(e)
        if e.kind in ("start", "retry"):
            resent.append(Event(e.time + 0.5, e.job, e.kind, e.attempt, "99.0" if e.kind == "retry" else e.detail))
    assert dedupe(resent) == ev
    assert replay(resent, res.runs) == res.runs


def test_late_duplicate_after_later_events():
    res = _run()
    first_start = res.events[0]
    late = res.events + [Event(100.0, first_start.job, first_start.kind, first_start.attempt)]
    assert replay(late, res.runs) == res.runs


def test_distinct_attempts_are_not_duplicates():
    events = [Event(0, "a", "start", 1), Event(1, "a", "retry", 1, "2"), Event(2, "a", "start", 2), Event(3, "a", "success", 2)]
    assert dedupe(events) == events
    assert dedupe(events + events) == events
