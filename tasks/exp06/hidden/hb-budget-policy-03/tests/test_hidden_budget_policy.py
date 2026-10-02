"""Hidden grader: per-pipeline budget policy (exp06 stratum B)."""

import json
from datetime import UTC, datetime

import pytest

from ledger import budget, cli, store

T = datetime(2026, 9, 2, 2, tzinfo=UTC)
V2 = {
    "version": 2,
    "defaults": {"monthly_usd": 500, "enforce": "alert", "max_run_usd": None},
    "pipelines": {
        "nightly": {"monthly_usd": 200, "enforce": None, "max_run_usd": 40},
        "hourly": {"monthly_usd": None, "enforce": "block"},
        "zero": {"monthly_usd": 0},
        "explore": {"enforce": "off"},
    },
}


def rec(run_id, pipeline, total):
    return store.RunRecord(run_id, pipeline, T, "success", total, {"j": total})


@pytest.fixture
def cfg_path(tmp_path):
    p = tmp_path / "budgets.json"
    p.write_text(json.dumps(V2))
    return p


def test_resolve_inheritance(cfg_path):
    cfg = budget.load_budgets(cfg_path)
    n = budget.resolve(cfg, "nightly")
    assert (n.monthly_usd, n.enforce, n.max_run_usd) == (200, "alert", 40)
    assert n.inherited == frozenset({"enforce"})
    h = budget.resolve(cfg, "hourly")
    assert (h.monthly_usd, h.enforce, h.max_run_usd) == (500, "block", None)
    assert h.inherited == frozenset({"monthly_usd", "max_run_usd"})
    z = budget.resolve(cfg, "zero")
    assert z.monthly_usd == 0 and "monthly_usd" not in z.inherited
    u = budget.resolve(cfg, "unknown-pipeline")
    assert u.inherited == frozenset({"monthly_usd", "enforce", "max_run_usd"}) and u.monthly_usd == 500
    assert budget.budget_for(cfg, "hourly") == 500


def test_defaults_fill_in(tmp_path):
    p = tmp_path / "b.json"
    p.write_text(json.dumps({"version": 2, "defaults": {"monthly_usd": 10}, "pipelines": {}}))
    pol = budget.resolve(budget.load_budgets(p), "x")
    assert (pol.enforce, pol.max_run_usd) == ("alert", None)


def test_bad_enforce_rejected(tmp_path):
    p = tmp_path / "b.json"
    p.write_text(json.dumps({"version": 2, "defaults": {"monthly_usd": 10}, "pipelines": {"a": {"enforce": "stop"}}}))
    with pytest.raises(ValueError):
        budget.resolve(budget.load_budgets(p), "a")


def test_v1_converts_without_rewriting(tmp_path):
    p = tmp_path / "b.json"
    original = json.dumps({"default_monthly_usd": 300, "pipelines": {"nightly": 120}})
    p.write_text(original)
    cfg = budget.load_budgets(p)
    assert cfg["version"] == 2
    assert cfg["defaults"] == {"monthly_usd": 300, "enforce": "alert", "max_run_usd": None}
    assert budget.resolve(cfg, "nightly").monthly_usd == 120
    assert budget.resolve(cfg, "nightly").inherited == frozenset({"enforce", "max_run_usd"})
    assert p.read_text() == original


def test_save_writes_v2(tmp_path, cfg_path):
    out = tmp_path / "out.json"
    budget.save_budgets(out, budget.load_budgets(cfg_path))
    assert out.read_text() == json.dumps(json.loads(out.read_text()), indent=2, sort_keys=True)
    assert json.loads(out.read_text())["version"] == 2


def test_reset_to_inherit_only_listed(cfg_path):
    cfg = budget.load_budgets(cfg_path)
    assert budget.reset_to_inherit(cfg, ["nightly", "zero"], "monthly_usd") == 2
    assert budget.resolve(cfg, "nightly").monthly_usd == 500 and budget.resolve(cfg, "nightly").max_run_usd == 40
    assert budget.resolve(cfg, "zero").monthly_usd == 500
    assert budget.resolve(cfg, "hourly").enforce == "block"
    assert budget.reset_to_inherit(cfg, ["nightly"], "monthly_usd") == 0
    with pytest.raises(KeyError):
        budget.reset_to_inherit(cfg, ["ghost"], "monthly_usd")
    with pytest.raises(ValueError):
        budget.reset_to_inherit(cfg, ["nightly"], "colour")


def test_governed_by_default(cfg_path):
    cfg = budget.load_budgets(cfg_path)
    assert budget.governed_by_default(cfg, ["nightly", "hourly", "zero", "explore", "new"]) == ["explore", "hourly", "new"]
    assert budget.governed_by_default(cfg, ["nightly", "hourly"], "enforce") == ["nightly"]


def test_check_skips_off(cfg_path):
    cfg = budget.load_budgets(cfg_path)
    records = [rec("1", "explore", 9999.0), rec("2", "zero", 0.01), rec("3", "nightly", 200.0), rec("4", "hourly", 600.0)]
    alerts = budget.check(records, cfg, "2026-09")
    assert [(a.pipeline, a.enforce) for a in alerts] == [("hourly", "block"), ("zero", "alert")]


def test_admit(cfg_path):
    cfg = budget.load_budgets(cfg_path)
    records = [rec("1", "hourly", 490.0), rec("2", "nightly", 150.0), rec("3", "explore", 1e6)]
    off = budget.admit(records, cfg, "explore", "2026-09", 1e6)
    assert off.allowed and off.reasons == ()
    ok = budget.admit(records, cfg, "hourly", "2026-09", 10.0)
    assert ok.allowed and ok.reasons == ()
    blocked = budget.admit(records, cfg, "hourly", "2026-09", 10.01)
    assert not blocked.allowed and any("monthly" in r for r in blocked.reasons)
    alerted = budget.admit(records, cfg, "nightly", "2026-09", 60.0)
    assert alerted.allowed
    assert len(alerted.reasons) == 2
    assert any("monthly" in r for r in alerted.reasons) and any("per-run cap" in r for r in alerted.reasons)
    p = budget.load_budgets(cfg_path)
    p["pipelines"]["nightly"]["enforce"] = "block"
    capped = budget.admit([], p, "nightly", "2026-09", 40.5)
    assert not capped.allowed and capped.reasons and all("per-run cap" in r for r in capped.reasons)


def test_cli_budget_set_and_reset(cfg_path, capsys):
    assert cli.main(["budget-set", "hourly", "--budgets", str(cfg_path), "--monthly-usd", "75", "--enforce", "inherit"]) == 0
    cfg = budget.load_budgets(cfg_path)
    assert cfg["pipelines"]["hourly"]["monthly_usd"] == 75 and cfg["pipelines"]["hourly"]["enforce"] is None
    assert cli.main(["budget-set", "brandnew", "--budgets", str(cfg_path), "--max-run-usd", "5"]) == 0
    pol = budget.resolve(budget.load_budgets(cfg_path), "brandnew")
    assert pol.max_run_usd == 5 and pol.inherited == frozenset({"monthly_usd", "enforce"})
    capsys.readouterr()
    assert cli.main(["budget-reset", "--budgets", str(cfg_path), "--field", "monthly_usd", "--pipelines", "hourly,nightly"]) == 0
    assert capsys.readouterr().out.strip() == "reset 2 pipeline(s)"
    assert budget.resolve(budget.load_budgets(cfg_path), "zero").monthly_usd == 0


def test_cli_summary(cfg_path, tmp_path, capsys):
    history = tmp_path / "h.jsonl"
    for r in (rec("1", "adhoc", 1.0), rec("2", "nightly", 2.0)):
        store.append(history, r)
    assert cli.main(["budget-summary", "--budgets", str(cfg_path), "--month", "2026-09", "--history", str(history)]) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert first == "default monthly budget $500.00 governs 3 of 5 pipelines"


def test_legacy_budgets_command(cfg_path, tmp_path, capsys):
    history = tmp_path / "h.jsonl"
    for r in (rec("1", "explore", 9999.0), rec("2", "nightly", 250.0)):
        store.append(history, r)
    code = cli.main(["budgets", "--month", "2026-09", "--budgets", str(cfg_path), "--history", str(history)])
    out = capsys.readouterr().out
    assert code == 1 and "nightly" in out and "explore" not in out
