from datetime import UTC, datetime

from ledger import budget, report, store


def rec(run_id, pipeline, day, total_minor):
    return store.RunRecord(run_id, pipeline, datetime(2026, 9, day, 2, tzinfo=UTC), "success", total_minor, {"j": total_minor})


def test_history_round_trip(tmp_path):
    path = tmp_path / "history.jsonl"
    store.append(path, rec("r1", "nightly", 1, 150))
    store.append(path, rec("r2", "hourly", 2, 25))
    loaded = store.load(path)
    assert [r.run_id for r in loaded] == ["r1", "r2"]
    assert store.query(loaded, pipeline="nightly")[0].total_minor == 150


def test_budget_alerts_use_default_and_overrides():
    records = [rec("r1", "nightly", 1, 15000), rec("r2", "nightly", 2, 10000), rec("r3", "hourly", 3, 2000)]
    config = {"default_monthly_usd": 10, "pipelines": {"nightly": 300}}
    alerts = budget.check(records, config, "2026-09")
    assert [(a.pipeline, a.budget_minor) for a in alerts] == [("hourly", 1000)]


def test_report_orders_by_spend():
    text = report.monthly_report([rec("r1", "a", 1, 100), rec("r2", "b", 1, 500)], "2026-09")
    lines = text.splitlines()
    assert lines[2].startswith("b") and lines[3].startswith("a")
