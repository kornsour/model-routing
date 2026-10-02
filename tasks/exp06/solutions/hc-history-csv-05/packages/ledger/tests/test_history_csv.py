from datetime import UTC, datetime

from ledger import report, store


def test_csv_follows_finance_conventions():
    rec = store.RunRecord("r1", "p", datetime(2026, 9, 1, 2, tzinfo=UTC), "success", 12.5, {})
    assert report.history_csv([rec], "2026-09").splitlines()[1] == "r1,p,2026-09-01T02:00:00Z,success,12.50"
