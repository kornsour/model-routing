import json
from pathlib import Path

import pytest

from model_routing.dashboard import build_payload
from model_routing.platform import Lab, configuration
from model_routing.quality import compare
from model_routing.store import connect, index_run, run_outcomes

ROOT = Path(__file__).resolve().parents[1]


def test_tracks_do_not_mix_vendors():
    for vendor in ("anthropic", "openai"):
        cfg = configuration(ROOT, dict(vendor=vendor))
        assert len({c.provider for c in cfg.candidates.values()}) == 1
        assert len({c.model for c in cfg.candidates.values()}) == 3
        assert all(r["kind"] != "oracle" and r.get("escalate_on") != "grader" for r in cfg.routers)
        assert len(configuration(ROOT, dict(vendor=vendor, track="research")).routers) == 9


def test_quality_gate_rejects_cheaper_wrong_and_partial():
    rows = [
        dict(router=r, task_id=str(i), trial=0, passed=p, cost_usd=c)
        for i in range(4)
        for r, p, c in [("all_strong", True, 1), ("cheap", i < 2, 0.1)]
    ]
    q = {r["router"]: r for r in compare(rows, "all_strong", 4)}
    assert q["cheap"]["status"] == "quality failed"
    assert q["cheap"]["regressions"] == 2
    assert compare(rows, "all_strong", 5)[0]["status"] == "incomplete"
    assert compare(rows, "missing", 4)[0]["status"] == "incomplete"


def test_saved_plan_fake_run_and_budget_validation(tmp_path):
    lab = Lab(ROOT, tmp_path)
    estimated = lab.estimate(dict(limit=2, trials=1, vendor="openai"))
    assert lab.jobs()[0]["state"] == "estimated"
    with pytest.raises(ValueError):
        lab.start(estimated["id"], float("nan"), True)
    lab.start(estimated["id"], 10, True)
    assert lab.lock.acquire(timeout=10)
    lab.lock.release()
    assert lab.jobs()[0]["state"] == "completed"
    assert json.loads(lab.jobs()[0]["spec"])["fake"]
    payload = build_payload(lab.db, include_synthetic=True)
    run = payload["runs"][0]
    assert run["track"] == "adoption" and run["vendor"] == "openai"
    assert len(run["quality"]) == 7
    assert all(q["status"] == "quality failed" for q in run["quality"])
    assert {o["difficulty"] for o in run["outcomes"]} != {"easy"}
    with pytest.raises(ValueError):
        lab.start(estimated["id"], 10, True)


def test_budget_stopped_is_not_completed(tmp_path):
    lab = Lab(ROOT, tmp_path)
    estimated = lab.estimate(dict(limit=2, trials=1))
    lab.start(estimated["id"], 0.000001, True)
    assert lab.lock.acquire(timeout=10)
    lab.lock.release()
    assert lab.jobs()[0]["state"] == "budget_stopped"


def test_exact_call_links_handle_zero_cost_and_unclaimed_calls(tmp_path):
    lab = Lab(ROOT, tmp_path)
    estimated = lab.estimate(dict(limit=1, trials=1, track="research"))
    lab.start(estimated["id"], 10, True)
    assert lab.lock.acquire(timeout=10)
    lab.lock.release()
    out = Path(lab.jobs()[0]["run_path"])
    outcomes = [json.loads(x) for x in (out / "outcomes.jsonl").read_text().splitlines()]
    calls = [json.loads(x) for x in (out / "calls.jsonl").read_text().splitlines()]
    for c in calls:
        c["cost_usd_list"] = 0
    for o in outcomes:
        o["cost_usd"] = 0
    (out / "calls.jsonl").write_text("\n".join(map(json.dumps, calls)))
    (out / "outcomes.jsonl").write_text("\n".join(map(json.dumps, outcomes)))
    with connect(lab.db) as conn:
        rid = index_run(conn, out)
        actual = run_outcomes(conn, rid)
    assert [[c["seq"] for c in o["calls"]] for o in actual] == [
        [c["seq"] for c in o["calls"]] for o in outcomes
    ]


def test_partial_run_never_qualifies_completed_subset():
    rows = [
        dict(router=r, task_id="one", trial=0, passed=True, cost_usd=c)
        for r, c in [("all_strong", 1), ("cheap", 0.1)]
    ]
    assert compare(rows, "all_strong", 1)[1]["status"].startswith("promising")
    assert all(
        q["status"] == "incomplete" for q in compare(rows, "all_strong", 1, run_complete=False)
    )
