import pytest

from orchestra import DAG, JobSpec, Scheduler, State, run
from orchestra.events import replay
from orchestra.store import dumps, loads


def J(name, *deps, **kw):
    return JobSpec(name, deps=deps, **kw)


def consistent(res):
    assert replay(res.events, res.runs) == res.runs
    again = loads(dumps(res))
    assert again.runs == res.runs and again.events == res.events


def test_no_cancellations_is_unchanged():
    specs = [J("a", duration=2), J("b", "a")]
    assert run(specs, cancel={}).events == run(specs).events
    assert Scheduler(DAG(specs)).run().events == run(specs).events


def test_cancel_running_job_releases_resources_and_cascades():
    specs = [
        J("load", duration=10, resources={"db": 1}),
        J("transform", "load"),
        J("publish", "transform"),
        J("other", resources={"db": 1}, duration=2),
    ]
    res = run(specs, {"db": 1}, cancel={"load": 3})
    load = res.runs["load"]
    assert load.state is State.CANCELLED
    assert load.finished_at == 3
    assert load.reason == "cancelled while running (attempt 1)"
    assert res.runs["transform"].state is State.CANCELLED
    assert res.runs["transform"].reason == "cancelled: upstream load"
    assert res.runs["publish"].reason == "cancelled: upstream load"
    assert res.runs["other"].started_at == 3
    assert res.makespan == 5
    at3 = [(e.job, e.kind) for e in res.events if e.time == 3]
    assert at3 == [("load", "cancelled"), ("transform", "cancelled"), ("publish", "cancelled"), ("other", "start")]
    consistent(res)


def test_cancel_without_cascade_fails_downstream():
    specs = [J("load", duration=10), J("transform", "load"), J("publish", "transform")]
    res = run(specs, cancel={"load": 3}, cascade=False)
    assert res.runs["load"].state is State.CANCELLED
    assert res.runs["transform"].state is State.UPSTREAM_FAILED
    assert res.runs["transform"].reason == "upstream load cancelled"
    assert res.runs["publish"].reason == "upstream transform upstream_failed"
    consistent(res)


def test_cancel_pending_job_before_it_starts():
    specs = [J("a", duration=5), J("b", "a"), J("c")]
    res = run(specs, cancel={"b": 1})
    b = res.runs["b"]
    assert b.state is State.CANCELLED and b.attempts == 0 and b.started_at is None
    assert b.reason == "cancelled" and b.finished_at == 1
    assert res.state("a") is State.SUCCESS
    assert res.makespan == 5
    ev = next(e for e in res.events if e.kind == "cancelled")
    assert (ev.time, ev.job, ev.attempt, ev.detail) == (1, "b", 0, "cancelled")
    consistent(res)


def test_cancel_at_time_zero():
    res = run([J("a"), J("b", "a")], cancel={"a": 0})
    assert res.state("a") is State.CANCELLED and res.runs["a"].attempts == 0
    assert res.state("b") is State.CANCELLED
    assert [e.kind for e in res.events] == ["cancelled", "cancelled"]
    assert res.makespan == 0


def test_cancel_after_completion_is_a_no_op():
    specs = [J("a", duration=2), J("b", "a", duration=2)]
    res = run(specs, cancel={"a": 2, "b": 50})
    assert res.state("a") is State.SUCCESS
    assert res.state("b") is State.SUCCESS
    assert res.runs["b"].started_at == 2
    assert res.makespan == 4
    assert not [e for e in res.events if e.kind == "cancelled"]
    consistent(res)


def test_cancel_job_waiting_to_retry():
    specs = [J("flaky", outcomes=("fail", "ok"), max_attempts=3, backoff=10), J("after", "flaky")]
    res = run(specs, cancel={"flaky": 1})
    # attempt 1 fails at 1 (completion first), then the cancellation hits the retry wait
    f = res.runs["flaky"]
    assert f.state is State.CANCELLED and f.attempts == 1 and f.retry_at is None
    assert f.reason == "cancelled"
    assert [e.kind for e in res.events if e.job == "flaky"] == ["start", "retry", "cancelled"]
    assert res.makespan == 1
    consistent(res)


def test_multiple_cancellations_same_time_in_name_order():
    specs = [J("z", duration=5), J("a", duration=5), J("child", "a", "z")]
    res = run(specs, cancel={"z": 2, "a": 2})
    at2 = [(e.job, e.detail) for e in res.events if e.time == 2]
    assert at2 == [
        ("a", "cancelled while running (attempt 1)"),
        ("child", "cancelled: upstream a"),
        ("z", "cancelled while running (attempt 1)"),
    ]
    consistent(res)


def test_cancelled_running_zero_duration_and_completion_order():
    specs = [J("a", duration=3), J("b", duration=3)]
    res = run(specs, cancel={"b": 3})
    # both complete at 3 before cancellations are processed
    assert res.state("b") is State.SUCCESS
    consistent(res)


def test_validation():
    with pytest.raises(ValueError):
        run([J("a")], cancel={"nope": 1})
    with pytest.raises(ValueError):
        run([J("a")], cancel={"a": -1})
    assert State.CANCELLED.terminal
    assert State.CANCELLED.value == "cancelled"


def test_cascade_skips_terminal_descendants():
    specs = [J("root", duration=1), J("fast", "root", duration=1), J("slow", "root", duration=9), J("end", "fast", "slow")]
    res = run(specs, cancel={"root": 5})
    # root already succeeded at 1 -> nothing is cancelled at all
    assert not [e for e in res.events if e.kind == "cancelled"]
    res2 = run(specs, cancel={"slow": 5})
    assert res2.state("fast") is State.SUCCESS
    assert res2.state("end") is State.CANCELLED
    assert res2.runs["end"].reason == "cancelled: upstream slow"
    assert res2.makespan == 5
    consistent(res2)
