"""Hidden grader: the eight platform incidents (exp06 stratum B)."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from orchestra import JobSpec, State, run
from orchestra.events import replay

from ledger import budget, inflight, pricing, store


def test_inc_4101_attempt_cap():
    result = run([JobSpec("load_orders", duration=1, outcomes=("fail",), max_attempts=3, backoff=1)])
    assert [e.kind for e in result.events].count("start") == 3
    assert result.runs["load_orders"].attempts == 3 and result.state("load_orders") is State.FAILED
    single = run([JobSpec("x", outcomes=("fail",))])
    assert single.runs["x"].attempts == 1


def test_inc_4102_first_failed_dependency_named():
    specs = [JobSpec("extract_orders", outcomes=("fail",)), JobSpec("extract_inventory", outcomes=("fail",)),
             JobSpec("publish_report", deps=("extract_orders", "extract_inventory"))]
    assert run(specs).runs["publish_report"].reason == "upstream extract_orders failed"
    specs = [JobSpec("z_first", outcomes=("fail",)), JobSpec("a_second", outcomes=("fail",)),
             JobSpec("r", deps=("z_first", "a_second"))]
    assert run(specs).runs["r"].reason == "upstream z_first failed"


def test_inc_4103_replay_matches_runs_exactly():
    specs = [JobSpec("a", outcomes=("fail", "ok"), max_attempts=2, backoff=1), JobSpec("b", deps=("a",)),
             JobSpec("c", outcomes=("fail",)), JobSpec("d", deps=("c",))]
    res = run(specs)
    assert replay(res.events, res.runs) == res.runs
    mid = [e for e in res.events if e.time <= 2]
    state = replay(mid, res.runs)["a"]
    assert state.state is State.RUNNING and state.retry_at is None


def test_inc_4104_retries_are_billed():
    specs = {"load_orders": JobSpec("load_orders", duration=20, outcomes=("fail", "fail", "ok"), max_attempts=3,
                                    backoff=1, resources={"warehouse": 2})}
    result = run(specs.values(), {"warehouse": 2})
    windows = pricing.attempt_windows(result)
    assert [w[:2] for w in windows] == [("load_orders", 1), ("load_orders", 2), ("load_orders", 3)]
    assert pricing.price_run(result, specs, {"warehouse": 0.5}).total == pytest.approx(3 * 20 * 2 * 0.5)


def test_inc_4105_months_are_utc():
    doc = {"version": 1, "run_id": "b1", "pipeline": "nightly", "started_at": "2026-10-01T01:30:00+02:00",
           "status": "success", "total_usd": 1.0, "jobs": {}}
    rec = store.RunRecord.from_dict(doc)
    assert rec.started_at == datetime(2026, 9, 30, 23, 30, tzinfo=UTC)
    assert rec.started_at.utcoffset() == timedelta(0)
    assert rec.month == "2026-09"
    assert store.query([rec], month="2026-09") == [rec]
    berlin = datetime.fromisoformat("2026-10-01T01:30:00+02:00")
    written = store.RunRecord("b2", "nightly", berlin, "success", 1.0, {}).to_dict()
    assert written["started_at"] == "2026-09-30T23:30:00+00:00"


def test_inc_4106_overlap_guard_is_per_pipeline(tmp_path):
    path = tmp_path / "inflight.json"
    t0 = datetime(2026, 9, 1, 1, tzinfo=UTC)
    inflight.start(path, "n1", "nightly", t0)
    assert inflight.already_running(path, "nightly")
    assert not inflight.already_running(path, "hourly")


def test_inc_4107_alert_only_over_budget():
    t = datetime(2026, 9, 2, tzinfo=UTC)
    at = [store.RunRecord("r1", "nightly", t, "success", 200.0, {})]
    config = {"default_monthly_usd": 500, "pipelines": {"nightly": 200}}
    assert budget.check(at, config, "2026-09") == []
    over = at + [store.RunRecord("r2", "nightly", t, "success", 0.01, {})]
    assert [a.pipeline for a in budget.check(over, config, "2026-09")] == ["nightly"]


def test_inc_4108_makespan_documented_behaviour_kept():
    result = run([JobSpec(n, duration=0) for n in ("a", "b", "c")])
    assert result.by_state(State.SUCCESS) == ["a", "b", "c"]
    assert result.makespan == 0.0
    assert run([JobSpec("a", duration=2), JobSpec("b", deps=("a",), duration=0)]).makespan == 2.0
