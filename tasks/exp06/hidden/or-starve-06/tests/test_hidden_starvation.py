import pytest

from orchestra import DAG, JobSpec, Scheduler, State, run
from orchestra.events import replay


def J(name, *deps, **kw):
    return JobSpec(name, deps=deps, **kw)


def stream(n, **kw):
    """A stream of small jobs that keeps one of two slots busy at all times."""
    return [J(f"s{i:03d}", resources={"slot": 1}, duration=1, priority=1, **kw) for i in range(n)]


def test_default_is_greedy_and_unchanged():
    specs = stream(6) + [J("big", resources={"slot": 2}, duration=1)]
    a = run(specs, {"slot": 2})
    b = run(specs, {"slot": 2}, policy="greedy")
    c = Scheduler(DAG(specs), {"slot": 2}).run()
    assert a.events == b.events == c.events
    assert a.runs["big"].started_at == 3


def test_reserve_blocks_lower_ranked_users_of_the_same_resource():
    specs = [
        J("small1", resources={"slot": 1}, duration=4, priority=9),
        J("big", resources={"slot": 2}, duration=1, priority=5),
        J("small2", resources={"slot": 1}, duration=1, priority=1),
        J("small3", resources={"slot": 1}, duration=1, priority=1),
        J("free", duration=1),
        J("other", resources={"io": 1}, duration=1, priority=0),
    ]
    greedy = run(specs, {"slot": 2, "io": 1})
    assert greedy.runs["small2"].started_at == 0
    assert greedy.runs["big"].started_at == 4
    res = run(specs, {"slot": 2, "io": 1}, policy="reserve")
    # t0: small1 starts; big blocked -> 'slot' closed; small2/small3 skipped; free and other start
    assert res.runs["small1"].started_at == 0
    assert res.runs["free"].started_at == 0
    assert res.runs["other"].started_at == 0
    assert res.runs["big"].started_at == 4
    assert res.runs["small2"].started_at == 5
    assert res.runs["small3"].started_at == 5
    assert replay(res.events, res.runs) == res.runs


def test_reserve_closes_all_kinds_of_a_blocked_candidate():
    specs = [
        J("hold_a", resources={"a": 1}, duration=3, priority=10),
        J("needs_ab", resources={"a": 1, "b": 1}, duration=1, priority=5),
        J("needs_b", resources={"b": 1}, duration=1, priority=1),
        J("needs_b_then_c", resources={"b": 1, "c": 1}, duration=1, priority=0),
        J("needs_c", resources={"c": 1}, duration=1, priority=-1),
    ]
    res = run(specs, {"a": 1, "b": 1, "c": 1}, policy="reserve")
    # needs_ab is blocked on 'a' -> closes a and b; needs_b skipped; needs_b_then_c skipped and
    # closes c too; needs_c skipped.
    assert res.runs["needs_ab"].started_at == 3
    assert res.runs["needs_b"].started_at == 4
    assert res.runs["needs_b_then_c"].started_at == 5
    assert res.runs["needs_c"].started_at == 6


def test_greedy_starves_big_job_reserve_does_not():
    specs = stream(40) + [J("big", resources={"slot": 2}, duration=1, priority=1)]
    greedy = run(specs, {"slot": 2})
    reserve = run(specs, {"slot": 2}, policy="reserve")
    # 'big' sorts before the s-jobs only by priority/name ties: b < s
    assert reserve.runs["big"].started_at == 0
    starving = stream(40) + [J("zbig", resources={"slot": 2}, duration=1, priority=1)]
    g = run(starving, {"slot": 2})
    assert g.runs["zbig"].started_at == 20
    assert greedy.state("big") is State.SUCCESS


def staggered():
    specs = [J("hog", resources={"slot": 1}, priority=5, duration=3), J("lo", resources={"slot": 1})]
    for i in range(10):
        specs.append(J(f"g{i}", duration=i + 1))
        specs.append(J(f"h{i}", f"g{i}", resources={"slot": 1}, priority=3))
    return specs


def test_aging_lets_an_old_job_overtake_newer_higher_priority_ones():
    plain = run(staggered(), {"slot": 1})
    assert plain.runs["lo"].started_at == 13
    aged = run(staggered(), {"slot": 1}, aging=2)
    # h_i becomes a candidate at i + 1; effective priority = priority + floor(waited / 2).
    # lo (waiting since 0) first strictly beats every other candidate at t = 10.
    starts = {e.job: e.time for e in aged.events if e.kind == "start"}
    assert [starts[f"h{i}"] for i in range(7)] == [3, 4, 5, 6, 7, 8, 9]
    assert starts["lo"] == 10
    assert starts["h7"] == 11
    assert replay(aged.events, aged.runs) == aged.runs


def test_aging_combines_with_reserve():
    specs = staggered() + [J("wide", resources={"slot": 1, "io": 1}, priority=4)]
    res = run(specs, {"slot": 1, "io": 1}, policy="reserve", aging=2)
    assert all(r.state is State.SUCCESS for r in res.runs.values())
    assert replay(res.events, res.runs) == res.runs


def test_validation():
    with pytest.raises(ValueError):
        run([J("a")], policy="fair")
    with pytest.raises(ValueError):
        run([J("a")], aging=0)
    with pytest.raises(ValueError):
        Scheduler(DAG([J("a")]), aging=-1)
