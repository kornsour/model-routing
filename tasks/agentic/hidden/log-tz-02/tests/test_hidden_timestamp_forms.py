from datetime import UTC, datetime, timedelta, timezone

import pytest
from logproc.cli import main
from logproc.parser import LogEntry
from logproc.pipeline import EntryWriter, build_report
from logproc.timestamps import parse_timestamp
from logproc.window import filter_window

TEN_UTC = datetime(2024, 3, 1, 10, 0, 0, tzinfo=UTC)


# Brief / README: every documented form parses, and "a timestamp with no Z and no offset is in
# UTC"; `12:00:00+02:00` is the same instant as `10:00:00Z`.
@pytest.mark.parametrize(
    "text, expected",
    [
        ("2024-03-01T10:00:00", TEN_UTC),
        ("2024-03-01 10:00:00", TEN_UTC),
        ("2024-03-01T10:00:00Z", TEN_UTC),
        ("2024-03-01T10:00:00.250", TEN_UTC + timedelta(milliseconds=250)),
        ("2024-03-01T10:00:00.250Z", TEN_UTC + timedelta(milliseconds=250)),
        ("2024-03-01T12:00:00+02:00", TEN_UTC),
        ("2024-03-01 04:30:00-05:30", TEN_UTC),
    ],
)
def test_parse_timestamp_documented_forms(text, expected):
    parsed = parse_timestamp(text)
    assert parsed == expected
    assert parsed.utcoffset() is not None  # comparable with every other parsed instant


# Brief: "timestamps that don't match any documented form must still be rejected with
# ValueError".
@pytest.mark.parametrize("text", ["yesterday", "2024/03/01 10:00:00", "10:00:00", ""])
def test_parse_timestamp_rejects_garbage(text):
    with pytest.raises(ValueError):
        parse_timestamp(text)


MIXED = [
    LogEntry("2024-03-01T10:00:01Z", "ERROR", "latest"),
    LogEntry("2024-03-01T12:00:00+02:00", "INFO", "middle"),
    LogEntry("2024-03-01 09:59:59", "INFO", "earliest"),
    LogEntry("2024-03-01T10:00:00.500", "WARNING", "half"),
]


def _write(path):
    writer = EntryWriter(path)
    for entry in MIXED:
        writer.write(entry)
    writer.close()


# Brief: the report on a mixed-format CSV must not crash and must order entries by instant.
def test_report_orders_mixed_formats_by_instant(tmp_path):
    out = tmp_path / "entries.csv"
    _write(out)
    summary = build_report(out)
    assert summary["count"] == 4
    assert summary["first"] == "2024-03-01 09:59:59"
    assert summary["last"] == "2024-03-01T10:00:01Z"


# Brief: "the report's ordering and its --since/--until window must compare instants correctly
# across formats".
def test_window_compares_instants_across_formats():
    kept = filter_window(MIXED, since="2024-03-01T10:00:00Z", until="2024-03-01 10:00:01")
    assert sorted(e.message for e in kept) == ["half", "middle"]
    kept = filter_window(MIXED, since="2024-03-01T05:00:00.000-05:00")
    assert sorted(e.message for e in kept) == ["half", "latest", "middle"]


# Brief: "`logproc report` fails on production logs" - the command itself must work, window
# included, on mixed formats.
def test_cli_report_with_window_on_mixed_formats(tmp_path, capsys):
    out = tmp_path / "entries.csv"
    _write(out)
    assert main(["report", str(out), "--since", "2024-03-01T12:00:00+02:00"]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("3 entries")
    assert "2024-03-01T10:00:01Z" in printed


# Brief: "compare instants correctly across formats" - a parsed instant must carry its offset so
# a mixed list sorts without a naive/aware TypeError, and a numeric offset is kept as given.
def test_offset_aware_result_type():
    assert parse_timestamp("2024-03-01T10:00:00").tzinfo is not None
    assert parse_timestamp("2024-03-01T12:00:00+02:00").utcoffset() == timezone(
        timedelta(hours=2)
    ).utcoffset(None)
