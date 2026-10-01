import json
import random

import pytest

from orchestra import JobSpec, State, run
from orchestra.cli import main
from orchestra.plan import critical_path, planned_duration


def J(name, *deps, **kw):
    return JobSpec(name, deps=deps, **kw)


PIPE = [
    J("extract", duration=2),
    J("clean", "extract", duration=3),
    J("lookup", duration=1),
    J("join", "clean", "lookup", duration=4),
    J("stats", "extract", duration=1),
    J("report", "join", "stats", duration=2),
]


def test_times_and_slack():
    p = critical_path(PIPE)
    j = p.jobs
    assert p.makespan == 11
    assert (j["extract"].earliest_start, j["extract"].earliest_finish) == (0, 2)
    assert (j["join"].earliest_start, j["join"].earliest_finish) == (5, 9)
    assert (j["report"].earliest_start, j["report"].earliest_finish) == (9, 11)
    assert (j["lookup"].latest_start, j["lookup"].latest_finish) == (4, 5)
    assert j["lookup"].slack == 4
    assert j["stats"].slack == 6
    assert (j["stats"].latest_start, j["stats"].latest_finish) == (8, 9)
    assert [n for n in j if j[n].critical] == ["extract", "clean", "join", "report"]
    assert p.critical_path == ["extract", "clean", "join", "report"]
    assert list(p.jobs) == ["extract", "clean", "lookup", "join", "stats", "report"]


def test_ties_pick_smallest_names():
    specs = [J("b0", duration=2), J("a0", duration=2), J("m", "a0", "b0", duration=1), J("x", "m"), J("w", "m")]
    p = critical_path(specs)
    assert p.critical_path == ["a0", "m", "w"]
    assert p.makespan == 4


def test_zero_duration_jobs():
    specs = [J("gate", duration=0), J("work", "gate", duration=3), J("tail", "work", duration=0)]
    p = critical_path(specs)
    assert p.critical_path == ["gate", "work", "tail"]
    assert p.makespan == 3
    assert p.jobs["tail"].earliest_start == 3


def test_retries_are_planned_like_the_scheduler():
    spec = J("flaky", duration=2, outcomes=("fail", "fail", "ok"), max_attempts=3, backoff=1)
    # 2 (fail) + 1 + 2 (fail) + 2 + 2 (ok) = 9
    assert planned_duration(spec) == (9, True)
    assert planned_duration(J("bad", duration=1, outcomes=("fail",), max_attempts=2, backoff=4)) == (6, False)
    assert planned_duration(J("capped", duration=1, outcomes=("fail",) * 3 + ("ok",), max_attempts=4, backoff=2, max_backoff=3)) == (1 + 2 + 1 + 3 + 1 + 3 + 1, True)


def test_failures_make_descendants_unreachable():
    specs = [
        J("a", duration=2),
        J("bad", "a", duration=1, outcomes=("fail",)),
        J("after", "bad", duration=5),
        J("after2", "after"),
        J("side", "a", duration=4),
    ]
    p = critical_path(specs)
    assert p.jobs["bad"].reachable and not p.jobs["bad"].succeeds
    assert p.jobs["bad"].earliest_finish == 3
    for n in ("after", "after2"):
        jp = p.jobs[n]
        assert not jp.reachable and not jp.succeeds
        assert jp.earliest_start is None and jp.latest_start is None and jp.slack is None
        assert not jp.critical
        assert jp.duration == 0
    assert p.makespan == 6
    assert p.critical_path == ["a", "side"]
    assert p.jobs["bad"].slack == 3


def test_empty_and_single():
    p = critical_path([])
    assert p.makespan == 0 and p.critical_path == [] and p.jobs == {}
    p1 = critical_path([J("only", duration=4)])
    assert p1.critical_path == ["only"] and p1.makespan == 4


@pytest.mark.parametrize("seed", range(25))
def test_matches_simulation_without_resource_limits(seed):
    rng = random.Random(seed)
    specs = []
    for i in range(rng.randrange(3, 60)):
        deps = tuple({specs[rng.randrange(i)].name for _ in range(rng.randrange(0, 3))}) if i else ()
        specs.append(
            J(
                f"n{i:02d}",
                *sorted(deps),
                duration=float(rng.choice([0, 1, 2, 3, 0.5])),
                outcomes=tuple(rng.choice(["ok", "ok", "fail"]) for _ in range(rng.randrange(1, 4))),
                max_attempts=rng.choice([1, 2, 3]),
                backoff=rng.choice([0, 1, 2.5]),
                priority=rng.randrange(-2, 3),
            )
        )
    res = run(specs)
    plan = critical_path(specs)
    assert plan.makespan == res.makespan
    for name, r in res.runs.items():
        jp = plan.jobs[name]
        if r.state in (State.SUCCESS, State.FAILED):
            assert jp.reachable
            assert jp.succeeds == (r.state is State.SUCCESS)
            assert jp.earliest_start == r.started_at
            assert jp.earliest_finish == r.finished_at
        else:
            assert r.state is State.UPSTREAM_FAILED
            assert not jp.reachable
    for a, b in zip(plan.critical_path, plan.critical_path[1:]):
        assert a in dict((s.name, s.deps) for s in specs)[b]
    if plan.critical_path:
        assert plan.jobs[plan.critical_path[-1]].earliest_finish == plan.makespan


def test_cli_plan_output(tmp_path, capsys):
    doc = {"jobs": [s.to_dict() for s in PIPE + [J("bad", duration=1, outcomes=("fail",)), J("never", "bad")]]}
    path = tmp_path / "p.json"
    path.write_text(json.dumps(doc))
    assert main(["plan", str(path)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "job       start  finish   slack  note",
        "bad           0       1      10  fails",
        "extract       0       2       0  critical",
        "clean         2       5       0  critical",
        "lookup        0       1       4",
        "join          5       9       0  critical",
        "never         -       -       -  unreachable",
        "stats         2       3       6",
        "report        9      11       0  critical",
        "critical path: extract -> clean -> join -> report (11)",
    ]


def test_cli_run_still_works(tmp_path, capsys):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"jobs": [s.to_dict() for s in PIPE]}))
    assert main(["run", str(path)]) == 0
    assert "makespan: 11" in capsys.readouterr().out
