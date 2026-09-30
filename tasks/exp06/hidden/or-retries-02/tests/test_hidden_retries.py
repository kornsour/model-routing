import hashlib

import pytest

from orchestra import JobSpec, State, run
from orchestra.events import replay
from orchestra.retry import backoff_delay, jitter_fraction
from orchestra.store import dumps, loads


def J(name, *deps, **kw):
    return JobSpec(name, deps=deps, **kw)


def frac(name, attempt):
    return int(hashlib.sha256(f"{name}:{attempt}".encode()).hexdigest()[:8], 16) / 2**32


def consistent(res):
    assert replay(res.events, res.runs) == res.runs
    again = loads(dumps(res))
    assert again.runs == res.runs and again.events == res.events


def test_max_attempts_counts_the_first_attempt():
    res = run([J("a", outcomes=("fail",), max_attempts=3)])
    assert res.runs["a"].attempts == 3
    assert res.state("a") is State.FAILED
    assert [e.kind for e in res.events] == ["start", "retry", "start", "retry", "start", "fail"]
    one = run([J("b", outcomes=("fail",), max_attempts=1)])
    assert one.runs["b"].attempts == 1 and one.state("b") is State.FAILED
    consistent(res)


def test_backoff_schedule():
    spec = J("a", backoff=2, max_backoff=5)
    assert [backoff_delay(spec, n) for n in (1, 2, 3, 4)] == [2, 4, 5, 5]
    res = run([J("a", outcomes=("fail",), max_attempts=4, backoff=1, duration=1)])
    starts = [e.time for e in res.events if e.kind == "start"]
    # 0-1 fail (+1) -> 2-3 fail (+2) -> 5-6 fail (+4) -> 10-11 fail
    assert starts == [0, 2, 5, 10]
    assert res.runs["a"].finished_at == 11
    assert res.makespan == 11
    consistent(res)


def test_jitter_is_deterministic_and_bounded():
    assert jitter_fraction("load", 1) == frac("load", 1)
    assert 0 <= jitter_fraction("x", 7) < 1
    spec = J("load", backoff=10, jitter=0.5)
    assert backoff_delay(spec, 1) == pytest.approx(10 * (1 + 0.5 * frac("load", 1)))
    assert backoff_delay(spec, 2) == pytest.approx(20 * (1 + 0.5 * frac("load", 2)))
    capped = J("load", backoff=10, max_backoff=12, jitter=1.0)
    assert backoff_delay(capped, 3) == pytest.approx(12 * (1 + frac("load", 3)))
    res = run([J("load", outcomes=("fail", "ok"), max_attempts=2, backoff=10, jitter=0.5, duration=1)])
    retry = next(e for e in res.events if e.kind == "retry")
    expected = 1 + 10 * (1 + 0.5 * frac("load", 1))
    assert float(retry.detail) == pytest.approx(expected)
    assert res.runs["load"].started_at == 0
    assert [e.time for e in res.events if e.kind == "start"][1] == pytest.approx(expected)
    consistent(res)


def test_resources_released_while_waiting_to_retry():
    specs = [
        J("flaky", outcomes=("fail", "ok"), max_attempts=2, backoff=5, resources={"db": 1}, priority=1),
        J("other", resources={"db": 1}, duration=2),
    ]
    res = run(specs, {"db": 1})
    # flaky 0-1 fails and waits until 6; other must use the slot at 1-3
    assert res.runs["other"].started_at == 1
    assert [e.time for e in res.events if e.job == "flaky" and e.kind == "start"] == [0, 6]
    consistent(res)


def test_retry_ready_job_competes_for_resources():
    specs = [
        J("flaky", outcomes=("fail", "ok"), max_attempts=2, backoff=1, resources={"db": 1}),
        J("hog", "gate", resources={"db": 1}, duration=5, priority=5),
        J("gate", duration=1),
    ]
    res = run(specs, {"db": 1})
    # t=1: flaky fails (retry at 2) and gate succeeds -> hog (higher priority) takes the slot 1-6;
    # flaky can only retry at 6.
    assert res.runs["hog"].started_at == 1
    assert [e.time for e in res.events if e.job == "flaky" and e.kind == "start"] == [0, 6]
    consistent(res)


def test_timeout_fails_attempt_at_timeout():
    res = run([J("slow", duration=10, timeout=3), J("next", "slow")])
    assert res.state("slow") is State.FAILED
    assert res.runs["slow"].finished_at == 3
    assert res.runs["slow"].reason == "attempt 1 timed out"
    assert res.state("next") is State.UPSTREAM_FAILED
    consistent(res)


def test_timeout_is_retryable_by_default_and_frees_resources():
    res = run(
        [
            J("slow", duration=10, timeout=3, max_attempts=2, backoff=1, resources={"cpu": 1}),
            J("x", resources={"cpu": 1}),
        ],
        {"cpu": 1},
    )
    assert [e.time for e in res.events if e.job == "slow" and e.kind == "start"] == [0, 4]
    assert res.runs["x"].started_at == 3
    assert res.runs["slow"].finished_at == 7
    assert res.runs["slow"].reason == "attempt 2 timed out"
    consistent(res)


def test_timeout_not_hit_when_duration_equals_timeout():
    res = run([J("edge", duration=3, timeout=3)])
    assert res.state("edge") is State.SUCCESS


def test_retry_on_controls_what_is_retried():
    no_timeout_retry = run([J("a", duration=5, timeout=1, max_attempts=3, retry_on=("fail",))])
    assert no_timeout_retry.runs["a"].attempts == 1
    assert no_timeout_retry.runs["a"].reason == "attempt 1 timed out"
    no_fail_retry = run([J("b", outcomes=("fail", "ok"), max_attempts=3, retry_on=("timeout",))])
    assert no_fail_retry.runs["b"].attempts == 1
    assert no_fail_retry.runs["b"].reason == "attempt 1 failed"
    both = run([J("c", outcomes=("fail", "ok"), max_attempts=3, retry_on=["fail", "timeout"])])
    assert both.state("c") is State.SUCCESS
    assert both.runs["c"].attempts == 2


def test_validation_and_round_trip():
    with pytest.raises(ValueError):
        JobSpec("x", timeout=0)
    with pytest.raises(ValueError):
        JobSpec("x", jitter=1.5)
    with pytest.raises(ValueError):
        JobSpec("x", retry_on=("oom",))
    spec = JobSpec("x", timeout=2.5, jitter=0.1, retry_on=("timeout",), max_attempts=4)
    assert JobSpec.from_dict(spec.to_dict()) == spec
    assert JobSpec("y").retry_on == ("fail", "timeout")
    assert JobSpec("y").timeout is None and JobSpec("y").jitter == 0.0


def test_pool_never_goes_negative_or_over():
    from orchestra import DAG, Scheduler

    specs = [
        J(f"j{i}", outcomes=("fail", "ok"), max_attempts=2, backoff=i % 3, resources={"s": 1 + i % 2}, duration=1 + i % 2)
        for i in range(12)
    ]
    sched = Scheduler(DAG(specs), {"s": 3})
    orig_acquire = sched.pool.acquire
    peak = []

    def spy(req):
        orig_acquire(req)
        peak.append(sched.pool.in_use["s"])

    sched.pool.acquire = spy
    res = sched.run()
    assert max(peak) <= 3
    assert sched.pool.in_use["s"] == 0
    assert all(r.state is State.SUCCESS for r in res.runs.values())
