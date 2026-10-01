import pytest

from orchestra import JobSpec, State, run
from orchestra.events import replay
from orchestra.store import dumps, loads


def J(name, *deps, **kw):
    return JobSpec(name, deps=deps, **kw)


def check_consistent(res):
    assert replay(res.events, res.runs) == res.runs
    again = loads(dumps(res))
    assert again.runs == res.runs and again.events == res.events


def test_default_trigger_unchanged():
    res = run([J("a", outcomes=("fail",)), J("b", "a"), J("c", "b")])
    assert res.state("b") is State.UPSTREAM_FAILED
    assert res.runs["b"].reason == "upstream a failed"
    assert res.runs["c"].reason == "upstream b upstream_failed"
    assert JobSpec("x").trigger == "all_success"
    check_consistent(res)


def test_all_done_runs_after_failure():
    res = run([J("a", outcomes=("fail",), duration=2), J("b", duration=5), J("report", "a", "b", trigger="all_done")])
    assert res.state("report") is State.SUCCESS
    assert res.runs["report"].started_at == 5
    check_consistent(res)


def test_all_done_waits_for_retries():
    res = run([
        J("a", outcomes=("fail", "fail", "ok"), max_attempts=3, backoff=1, duration=1),
        J("cleanup", "a", trigger="all_done"),
    ])
    # a: 0-1 fail, retry at 2; 2-3 fail, retry at 5; 5-6 ok
    assert res.runs["cleanup"].started_at == 6
    check_consistent(res)


def test_one_failed_cleanup_and_skip():
    res = run([
        J("extract"),
        J("load", "extract", outcomes=("fail",), duration=3),
        J("alert", "extract", "load", trigger="one_failed"),
    ])
    assert res.state("alert") is State.SUCCESS
    assert res.runs["alert"].started_at == 4
    ok = run([J("extract"), J("load", "extract"), J("alert", "extract", "load", trigger="one_failed")])
    assert ok.state("alert") is State.SKIPPED
    assert ok.runs["alert"].reason == "no upstream failed"
    assert ok.runs["alert"].finished_at == 2
    assert ok.runs["alert"].attempts == 0 and ok.runs["alert"].started_at is None
    check_consistent(res)
    check_consistent(ok)


def test_one_failed_fires_early():
    res = run([J("a", outcomes=("fail",), duration=1), J("b", duration=10), J("page", "a", "b", trigger="one_failed")])
    assert res.runs["page"].started_at == 1
    check_consistent(res)


def test_one_failed_on_upstream_failed():
    res = run([J("a", outcomes=("fail",)), J("b", "a"), J("c", "b", trigger="one_failed")])
    assert res.state("b") is State.UPSTREAM_FAILED
    assert res.state("c") is State.SUCCESS
    assert res.runs["c"].started_at == 1
    check_consistent(res)


def test_skip_propagates_through_all_success():
    res = run([
        J("a"),
        J("on_fail", "a", trigger="one_failed"),
        J("after", "on_fail"),
        J("after2", "after"),
        J("done", "after2", trigger="all_done"),
        J("guard", "after2", trigger="none_failed"),
    ])
    assert res.state("on_fail") is State.SKIPPED
    assert res.state("after") is State.SKIPPED
    assert res.runs["after"].reason == "upstream on_fail skipped"
    assert res.state("after2") is State.SKIPPED
    assert res.state("done") is State.SUCCESS
    assert res.state("guard") is State.SUCCESS
    # everything resolved in the same step at t=1, so done/guard start at 1
    assert res.runs["done"].started_at == 1
    kinds = [(e.job, e.kind) for e in res.events if e.time == 1]
    assert kinds[:4] == [("a", "success"), ("on_fail", "skipped"), ("after", "skipped"), ("after2", "skipped")]
    check_consistent(res)


def test_failure_beats_skip_for_all_success():
    res = run([
        J("a"),
        J("s", "a", trigger="one_failed"),
        J("f", outcomes=("fail",)),
        J("x", "s", "f"),
    ])
    assert res.state("x") is State.UPSTREAM_FAILED
    assert res.runs["x"].reason == "upstream f failed"
    check_consistent(res)


def test_one_success():
    res = run([
        J("mirror1", outcomes=("fail",), duration=1),
        J("mirror2", duration=3),
        J("mirror3", duration=9),
        J("fetch_any", "mirror1", "mirror2", "mirror3", trigger="one_success"),
    ])
    assert res.runs["fetch_any"].started_at == 3
    none = run([
        J("m1", outcomes=("fail",)),
        J("m2", outcomes=("fail",), duration=2),
        J("any", "m1", "m2", trigger="one_success"),
    ])
    assert none.state("any") is State.UPSTREAM_FAILED
    assert none.runs["any"].reason == "upstream m1 failed"
    assert none.runs["any"].finished_at == 2
    skip = run([J("a"), J("s", "a", trigger="one_failed"), J("any", "s", trigger="one_success")])
    assert skip.state("any") is State.SKIPPED
    assert skip.runs["any"].reason == "no upstream succeeded"
    for r in (res, none, skip):
        check_consistent(r)


def test_none_failed():
    res = run([
        J("a"),
        J("s", "a", trigger="one_failed"),
        J("b", duration=4),
        J("n", "s", "b", trigger="none_failed"),
    ])
    assert res.state("n") is State.SUCCESS and res.runs["n"].started_at == 4
    bad = run([J("f", outcomes=("fail",)), J("slow", duration=9), J("n", "f", "slow", trigger="none_failed")])
    assert bad.state("n") is State.UPSTREAM_FAILED
    assert bad.runs["n"].finished_at == 1
    assert bad.runs["n"].reason == "upstream f failed"
    check_consistent(res)
    check_consistent(bad)


def test_makespan_ignores_skipped_and_counts_by_state():
    res = run([J("a", duration=3), J("s", "a", trigger="one_failed")])
    assert res.makespan == 3
    assert res.by_state(State.SKIPPED) == ["s"]
    assert State.SKIPPED.terminal


def test_trigger_validation_and_dict_round_trip():
    with pytest.raises(ValueError):
        JobSpec("x", trigger="sometimes")
    spec = JobSpec.from_dict({"name": "r", "deps": ["a"], "trigger": "all_done"})
    assert spec.trigger == "all_done"
    assert JobSpec.from_dict(spec.to_dict()) == spec


def test_root_job_with_trigger_just_runs():
    res = run([J("solo", trigger="one_failed")])
    assert res.state("solo") is State.SUCCESS


def test_resources_and_priority_still_apply():
    res = run(
        [
            J("a", outcomes=("fail",), resources={"slot": 1}),
            J("b", resources={"slot": 1}, duration=2),
            J("fix", "a", trigger="one_failed", resources={"slot": 1}, priority=9),
            J("c", resources={"slot": 1}),
        ],
        {"slot": 1},
    )
    # t0: a starts (priority ties -> name); t1: a fails, fix (prio 9) starts before b/c
    assert res.runs["fix"].started_at == 1
    assert res.runs["b"].started_at == 2
    assert res.runs["c"].started_at == 4
    check_consistent(res)
