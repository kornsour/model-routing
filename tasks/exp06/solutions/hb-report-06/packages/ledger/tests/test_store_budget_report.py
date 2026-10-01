from datetime import UTC, datetime

from ledger import budget, report, store


def rec(run_id, pipeline, day, total):
    return store.RunRecord(run_id, pipeline, datetime(2026, 9, day, 2, tzinfo=UTC), "success", total, {"j": total})


def test_history_round_trip(tmp_path):
    path = tmp_path / "history.jsonl"
    store.append(path, rec("r1", "nightly", 1, 1.5))
    store.append(path, rec("r2", "hourly", 2, 0.25))
    loaded = store.load(path)
    assert [r.run_id for r in loaded] == ["r1", "r2"]
    assert store.query(loaded, pipeline="nightly")[0].total_usd == 1.5


def test_budget_alerts_use_default_and_overrides():
    records = [rec("r1", "nightly", 1, 150.0), rec("r2", "nightly", 2, 100.0), rec("r3", "hourly", 3, 20.0)]
    config = {"default_monthly_usd": 10, "pipelines": {"nightly": 300}}
    alerts = budget.check(records, config, "2026-09")
    assert [(a.pipeline, a.budget_usd) for a in alerts] == [("hourly", 10.0)]


def test_report_orders_by_spend():
    text = report.monthly_report([rec("r1", "a", 1, 1.0), rec("r2", "b", 1, 5.0)], "2026-09")
    lines = text.splitlines()
    assert lines[2].startswith("b") and lines[3].startswith("a")


def test_first_of_month_belongs_to_previous_month_in_chicago():
    r = store.RunRecord("r", "nightly", datetime(2026, 9, 1, 2, tzinfo=UTC), "success", 1.0, {})
    assert r.month_in("America/Chicago") == "2026-08"


def test_rows_add_up_after_display_rounding():
    records = [rec("a", "a", 1, 0.005), rec("b", "b", 1, 0.015)]
    text = report.monthly_report(records, "2026-09")
    assert text.splitlines()[-1].endswith("$      0.02")
