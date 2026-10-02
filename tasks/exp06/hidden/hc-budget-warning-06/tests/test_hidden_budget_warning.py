"""Hidden grader: early budget warnings (exp06 stratum C; keyed interpretation)."""

import json
from datetime import UTC, datetime

from ledger import cli, store

T = datetime(2026, 9, 3, tzinfo=UTC)


def _setup(tmp_path, spends, extra=None):
    history = tmp_path / "h.jsonl"
    for i, (pipeline, usd) in enumerate(spends):
        store.append(history, store.RunRecord(f"r{i}", pipeline, T, "success", usd, {}))
    budgets = tmp_path / "budgets.json"
    budgets.write_text(json.dumps({"default_monthly_usd": 200, "pipelines": {"big": 1000}, **(extra or {})}))
    return ["budgets", "--month", "2026-09", "--budgets", str(budgets), "--history", str(history)]


def test_warning_only_exits_zero(tmp_path, capsys):
    args = _setup(tmp_path, [("hourly", 170.0), ("calm", 100.0), ("edge", 160.0), ("full", 200.0)])
    assert cli.main(args) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "WARN hourly: $170.00 of $200.00" in lines
    assert "WARN edge: $160.00 of $200.00" in lines
    assert "WARN full: $200.00 of $200.00" in lines
    assert not any("calm" in line for line in lines)
    assert not any(line.startswith("OVER") for line in lines)


def test_over_still_exits_one_and_is_not_also_warned(tmp_path, capsys):
    args = _setup(tmp_path, [("nightly", 201.5), ("hourly", 170.0)])
    assert cli.main(args) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "OVER nightly: $201.50 of $200.00" in lines
    assert "WARN hourly: $170.00 of $200.00" in lines
    assert not any(line.startswith("WARN nightly") for line in lines)


def test_warn_fraction_override(tmp_path, capsys):
    args = _setup(tmp_path, [("hourly", 170.0), ("big", 950.0)], {"warn_fraction": 0.9})
    assert cli.main(args) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["WARN big: $950.00 of $1000.00"]


def test_quiet_when_nothing_close(tmp_path, capsys):
    args = _setup(tmp_path, [("hourly", 10.0)])
    assert cli.main(args) == 0
    assert capsys.readouterr().out == ""
