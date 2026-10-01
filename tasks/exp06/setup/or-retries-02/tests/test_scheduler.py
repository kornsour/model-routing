import pytest

from orchestra import DAG, CycleError, DagError, JobSpec, State, run
from orchestra.events import replay
from orchestra.pool import PoolError
from orchestra.store import dumps, loads


def J(name, *deps, **kw):
    return JobSpec(name, deps=deps, **kw)


def test_linear_chain():
    res = run([J("a", duration=2), J("b", "a", duration=3), J("c", "b")])
    assert [res.state(n) for n in "abc"] == [State.SUCCESS] * 3
    assert res.runs["c"].started_at == 5
    assert res.makespan == 6


def test_parallel_with_capacity():
    specs = [J(n, resources={"slot": 1}, duration=2) for n in "abcd"]
    res = run(specs, {"slot": 2})
    assert [res.runs[n].started_at for n in "abcd"] == [0, 0, 2, 2]
    assert res.makespan == 4


def test_priority_order():
    specs = [J("a", resources={"slot": 1}), J("b", resources={"slot": 1}, priority=5)]
    res = run(specs, {"slot": 1})
    assert res.runs["b"].started_at == 0 and res.runs["a"].started_at == 1


def test_retry_then_success():
    res = run([J("a", outcomes=("fail", "ok"), max_attempts=3, backoff=2, duration=1)])
    assert res.state("a") is State.SUCCESS
    assert res.runs["a"].attempts == 2
    assert [e.kind for e in res.events] == ["start", "retry", "start", "success"]


def test_failure_propagates():
    res = run([J("a", outcomes=("fail",)), J("b", "a"), J("c", "b"), J("d")])
    assert res.by_state(State.UPSTREAM_FAILED) == ["b", "c"]
    assert res.state("a") is State.FAILED and res.state("d") is State.SUCCESS


def test_validation():
    with pytest.raises(CycleError):
        DAG([J("a", "b"), J("b", "a")])
    with pytest.raises(DagError):
        DAG([J("a", "zzz")])
    with pytest.raises(PoolError):
        run([J("a", resources={"slot": 3})], {"slot": 2})


def test_replay_and_store_round_trip():
    specs = [J("a", outcomes=("fail", "ok"), max_attempts=2), J("b", "a"), J("c", outcomes=("fail",)), J("d", "c")]
    res = run(specs)
    assert replay(res.events, res.runs) == res.runs
    again = loads(dumps(res))
    assert again.runs == res.runs and again.events == res.events
