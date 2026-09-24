import csv

from logproc.cli import main
from logproc.csvexport import export_csv, import_csv
from logproc.parser import LogEntry
from logproc.pipeline import build_report, process_log, read_entries

TRACE_LOG = (
    "2024-03-01T10:00:00 INFO server started\n"
    "2024-03-01T10:00:01 ERROR request failed\n"
    "Traceback (most recent call last):\n"
    '  File "app.py", line 12, in handle\n'
    '    raise ValueError("bad, input")\n'
    "ValueError: bad, input\n"
    "2024-03-01T10:00:02 INFO still running\n"
)
TRACE_MESSAGE = (
    "request failed\n"
    "Traceback (most recent call last):\n"
    '  File "app.py", line 12, in handle\n'
    '    raise ValueError("bad, input")\n'
    "ValueError: bad, input"
)


# Brief: "continuation lines ... become part of the preceding entry's message, joined with
# newlines, and the entry count is unchanged (a traceback is not extra entries)".
def test_read_entries_attaches_continuation_lines(tmp_path):
    log = tmp_path / "app.log"
    log.write_text(TRACE_LOG)
    entries = read_entries(log)
    assert [e.level for e in entries] == ["INFO", "ERROR", "INFO"]
    assert entries[1].message == TRACE_MESSAGE
    assert entries[2].message == "still running"


# Brief: "a continuation line with no preceding entry is skipped".
def test_leading_continuation_line_is_skipped(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("  stray continuation\n2024-03-01T10:00:00 INFO ok\n")
    entries = read_entries(log)
    assert [e.message for e in entries] == ["ok"]


# Brief: "the CSV importer [reads] the message intact, line breaks included" and the CSV must
# stay standard RFC 4180 (embedded commas, quotes and newlines round-trip).
def test_export_import_roundtrip_preserves_newlines_commas_quotes(tmp_path):
    message = 'first line, with comma\n  second "quoted" line\nthird'
    entries = [LogEntry("2024-03-01T10:00:00", "ERROR", message)]
    path = tmp_path / "entries.csv"
    export_csv(entries, path)
    imported = import_csv(path)
    assert len(imported) == 1
    assert imported[0].message == message
    # RFC 4180: a standard reader must see exactly one data row with three fields.
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["timestamp", "level", "message"]
    assert rows[1:] == [["2024-03-01T10:00:00", "ERROR", message]]


# Brief: "the entries CSV that `process` writes must be readable back by `report` ... with the
# message intact, line breaks included".
def test_process_writes_multiline_message_that_report_reads(tmp_path):
    log = tmp_path / "app.log"
    log.write_text(TRACE_LOG)
    out = tmp_path / "entries.csv"
    process_log(log, out).close()
    summary = build_report(out)
    assert summary["count"] == 3
    assert summary["by_level"] == {"INFO": 2, "ERROR": 1}
    assert import_csv(out)[1].message == TRACE_MESSAGE


# Brief: "appending a second run to an existing entries CSV must not corrupt earlier
# multi-line messages".
def test_second_run_appends_without_corrupting_earlier_traceback(tmp_path):
    log = tmp_path / "app.log"
    log.write_text(TRACE_LOG)
    out = tmp_path / "entries.csv"
    process_log(log, out).close()
    second = tmp_path / "second.log"
    second.write_text("2024-03-01T11:00:00 WARNING disk low\n")
    process_log(second, out).close()
    entries = import_csv(out)
    assert [e.level for e in entries] == ["INFO", "ERROR", "INFO", "WARNING"]
    assert entries[1].message == TRACE_MESSAGE
    assert build_report(out)["count"] == 4


# Brief: "`logproc process` on a log containing Python tracebacks" must count the traceback's
# entry once (the CLI is the user-facing surface for the symptom).
def test_cli_process_counts_traceback_once(tmp_path, capsys):
    log = tmp_path / "app.log"
    log.write_text(TRACE_LOG)
    out = tmp_path / "entries.csv"
    assert main(["process", str(log), "--out", str(out)]) == 0
    assert "3 entries" in capsys.readouterr().out
