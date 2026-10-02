"""Hidden grader: finance-ready monthly report (exp06 stratum B)."""

from datetime import UTC, datetime

import pytest

from ledger import cli, report, store


def rec(run_id, pipeline, when, total):
    return store.RunRecord(run_id, pipeline, when, "success", total, {"j": total})


def test_month_in_and_query_tz():
    r = rec("r1", "nightly", datetime(2026, 10, 1, 2, tzinfo=UTC), 5.0)
    assert r.month == "2026-10" and r.month_in("UTC") == "2026-10"
    assert r.month_in("America/Chicago") == "2026-09"
    assert r.month_in("Asia/Tokyo") == "2026-10"
    assert store.query([r], month="2026-09", tz="America/Chicago") == [r]
    assert store.query([r], month="2026-09") == []


def test_nearest_rank_percentiles():
    records = [rec(f"n{i}", "nightly", datetime(2026, 9, 2, tzinfo=UTC), float(v)) for i, v in enumerate([5, 1, 4, 2, 3])]
    records.append(rec("solo", "solo", datetime(2026, 9, 2, tzinfo=UTC), 7.0))
    twenty = [rec(f"h{i}", "hourly", datetime(2026, 9, 3, tzinfo=UTC), float(i + 1)) for i in range(20)]
    rows = {r.pipeline: r for r in report.monthly_rows(records + twenty, "2026-09")}
    n = rows["nightly"]
    assert (n.runs, n.total_usd, n.p50_usd, n.p95_usd, n.max_usd) == (5, 15.0, 3.0, 5.0, 5.0)
    s = rows["solo"]
    assert (s.p50_usd, s.p95_usd, s.max_usd) == (7.0, 7.0, 7.0)
    h = rows["hourly"]
    assert (h.p50_usd, h.p95_usd) == (10.0, 19.0)
    assert [r.pipeline for r in report.monthly_rows(records + twenty, "2026-09")] == ["hourly", "nightly", "solo"]


def _rounding_records():
    t = datetime(2026, 9, 5, tzinfo=UTC)
    return [rec("a", "alpha", t, 0.005), rec("b", "beta", t, 0.015), rec("c", "gamma", t, 1234.5)]


def test_text_render_rows_add_up():
    text = report.monthly_report(_rounding_records(), "2026-09")
    assert text == (
        "Spend for 2026-09\n\n"
        f"{'gamma':<24} {1:>4} runs  ${1234.5:>10.2f}\n"
        f"{'beta':<24} {1:>4} runs  ${0.02:>10.2f}\n"
        f"{'alpha':<24} {1:>4} runs  ${0.0:>10.2f}\n"
        "\n"
        f"{'total':<24} {3:>4} runs  ${1234.52:>10.2f}\n"
    )
    assert report.render_text(report.monthly_rows(_rounding_records(), "2026-09"), "2026-09") == text


def test_csv_render():
    t = datetime(2026, 9, 5, tzinfo=UTC)
    rows = report.monthly_rows(_rounding_records() + [rec("d", "odd,name", t, 2.0), rec("e", "odd,name", t, 3.0)], "2026-09")
    assert report.render_csv(rows) == (
        "pipeline,runs,total_usd,p50_usd,p95_usd,max_usd\n"
        "gamma,1,1234.50,1234.50,1234.50,1234.50\n"
        '"odd,name",2,5.00,2.00,3.00,3.00\n'
        "beta,1,0.02,0.02,0.02,0.02\n"
        "alpha,1,0.00,0.00,0.00,0.00\n"
        "TOTAL,5,1239.52,,,\n"
    )


def test_markdown_render():
    t = datetime(2026, 9, 5, tzinfo=UTC)
    rows = report.monthly_rows(_rounding_records() + [rec("d", "a|b", t, 2.0)], "2026-09")
    assert report.render_markdown(rows, "2026-09", "America/Chicago") == (
        "## Spend for 2026-09 (America/Chicago)\n"
        "\n"
        "| pipeline | runs | total | p50 | p95 | max |\n"
        "|---|---:|---:|---:|---:|---:|\n"
        "| gamma | 1 | $1,234.50 | $1,234.50 | $1,234.50 | $1,234.50 |\n"
        "| a\\|b | 1 | $2.00 | $2.00 | $2.00 | $2.00 |\n"
        "| beta | 1 | $0.02 | $0.02 | $0.02 | $0.02 |\n"
        "| alpha | 1 | $0.00 | $0.00 | $0.00 | $0.00 |\n"
        "| **total** | 4 | **$1,236.52** | | | |\n"
    )


def test_empty_month():
    assert report.render_csv([]) == "pipeline,runs,total_usd,p50_usd,p95_usd,max_usd\nTOTAL,0,0.00,,,\n"
    md = report.render_markdown([], "2026-09", "UTC")
    assert md.endswith("| **total** | 0 | **$0.00** | | | |\n")
    assert report.monthly_report([], "2026-09").endswith(f"{'total':<24} {0:>4} runs  ${0:>10.2f}\n")


def test_cli_formats_and_tz(tmp_path, capsys):
    history = tmp_path / "h.jsonl"
    store.append(history, rec("r1", "nightly", datetime(2026, 10, 1, 2, tzinfo=UTC), 12.0))
    store.append(history, rec("r2", "nightly", datetime(2026, 9, 15, 2, tzinfo=UTC), 3.0))
    assert cli.main(["report", "--month", "2026-09", "--tz", "America/Chicago", "--format", "csv", "--history", str(history)]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[1] == "nightly,2,15.00,3.00,12.00,12.00"
    assert cli.main(["report", "--month", "2026-09", "--history", str(history)]) == 0
    assert "$      3.00" in capsys.readouterr().out
    assert cli.main(["report", "--month", "2026-09", "--format", "markdown", "--tz", "UTC", "--history", str(history)]) == 0
    assert capsys.readouterr().out.startswith("## Spend for 2026-09 (UTC)\n")
    code = cli.main(["report", "--month", "2026-09", "--tz", "Mars/Olympus", "--history", str(history)])
    err = capsys.readouterr().err
    assert code == 2 and "unknown time zone: Mars/Olympus" in err
