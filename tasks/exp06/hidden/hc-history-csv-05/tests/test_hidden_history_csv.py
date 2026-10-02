"""Hidden grader: finance run-history CSV (exp06 stratum C; keyed interpretation)."""

from datetime import UTC, datetime, timedelta, timezone

from ledger import cli, report, store


def _records():
    return [
        store.RunRecord("r3", "hourly", datetime(2026, 9, 2, 1, tzinfo=UTC), "success", 0.125, {}),
        store.RunRecord("r1", "nightly, eu", datetime(2026, 9, 1, 2, tzinfo=UTC), "success", 12.5, {}),
        store.RunRecord("r2", "hourly", datetime(2026, 9, 2, 1, tzinfo=UTC), "failed", 0.135, {}),
        store.RunRecord("r9", "nightly", datetime(2026, 10, 1, 0, 30, tzinfo=timezone(timedelta(hours=2))), "success", 3.0, {}),
        store.RunRecord("r0", "nightly", datetime(2026, 8, 31, 23, tzinfo=UTC), "success", 1.0, {}),
    ]


EXPECTED = (
    "run_id,pipeline,started_at,status,total_usd\n"
    'r1,"nightly, eu",2026-09-01T02:00:00Z,success,12.50\n'
    "r2,hourly,2026-09-02T01:00:00Z,failed,0.14\n"
    "r3,hourly,2026-09-02T01:00:00Z,success,0.12\n"
    "r9,nightly,2026-09-30T22:30:00Z,success,3.00\n"
)


def test_history_csv():
    assert report.history_csv(_records(), "2026-09") == EXPECTED


def test_empty_month():
    assert report.history_csv(_records(), "2026-01") == "run_id,pipeline,started_at,status,total_usd\n"


def test_cli(tmp_path, capsys):
    path = tmp_path / "h.jsonl"
    for r in _records():
        store.append(path, r)
    assert cli.main(["history-csv", "--month", "2026-09", "--history", str(path)]) == 0
    assert capsys.readouterr().out == EXPECTED
