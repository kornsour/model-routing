from logproc.parser import LogEntry
from logproc.pipeline import EntryWriter, build_report
from logproc.window import filter_window

ENTRIES = [
    LogEntry("2024-03-01T10:00:00", "INFO", "a"),
    LogEntry("2024-03-01 10:00:05", "ERROR", "b"),
    LogEntry("2024-03-01T10:00:09", "INFO", "c"),
]


def test_filter_window_plain_formats():
    kept = filter_window(ENTRIES, since="2024-03-01T10:00:03", until="2024-03-01 10:00:09")
    assert [e.message for e in kept] == ["b"]


def test_report_first_last_and_window(tmp_path):
    out = tmp_path / "entries.csv"
    writer = EntryWriter(out)
    for entry in reversed(ENTRIES):
        writer.write(entry)
    writer.close()
    summary = build_report(out)
    assert summary["first"] == "2024-03-01T10:00:00"
    assert summary["last"] == "2024-03-01T10:00:09"
    assert build_report(out, since="2024-03-01T10:00:05")["count"] == 2
