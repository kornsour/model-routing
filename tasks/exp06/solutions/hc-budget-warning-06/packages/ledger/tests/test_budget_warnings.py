from datetime import UTC, datetime

from ledger import budget, store


def test_warn_at_eighty_percent():
    recs = [store.RunRecord("r", "p", datetime(2026, 9, 1, tzinfo=UTC), "success", 80.0, {})]
    assert [w.pipeline for w in budget.warnings(recs, {"default_monthly_usd": 100}, "2026-09")] == ["p"]
