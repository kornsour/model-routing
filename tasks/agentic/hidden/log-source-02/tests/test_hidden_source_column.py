import csv

from logproc.cli import main
from logproc.csvexport import export_csv, import_csv
from logproc.parser import LogEntry
from logproc.pipeline import EntryWriter, build_report, process_log

OLD_FORMAT = (
    "timestamp,level,message\n"
    "2024-03-01T10:00:00,INFO,server started\n"
    "2024-03-01T10:00:01,ERROR,boom\n"
)


# Brief: "the visible tests construct `LogEntry(ts, level, msg)` positionally and must keep
# passing" - an entry made the old way has an empty source.
def test_entry_without_source_defaults_to_empty():
    entry = LogEntry("2024-03-01T10:00:00", "INFO", "started")
    assert entry.source == ""


# Brief: "entries CSVs written by the current version (three columns, no source) must still
# load everywhere they load today, with an empty source".
def test_old_three_column_csv_still_imports(tmp_path):
    path = tmp_path / "entries.csv"
    path.write_text(OLD_FORMAT)
    entries = import_csv(path)
    assert [(e.level, e.message, e.source) for e in entries] == [
        ("INFO", "server started", ""),
        ("ERROR", "boom", ""),
    ]


# Brief: "carried as a fourth CSV column `source`, after `message`" and it must round-trip.
def test_export_import_roundtrip_carries_source(tmp_path):
    path = tmp_path / "entries.csv"
    export_csv([LogEntry("2024-03-01T10:00:00", "INFO", "started", "api.log")], path)
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["timestamp", "level", "message", "source"]
    assert rows[1] == ["2024-03-01T10:00:00", "INFO", "started", "api.log"]
    assert import_csv(path)[0].source == "api.log"


# Brief: "set by the pipeline to the log file's base name (e.g. `app.log`)" - through the
# writer the CLI uses, not just the exporter.
def test_process_log_tags_entries_with_log_basename(tmp_path):
    log = tmp_path / "logs" / "api.log"
    log.parent.mkdir()
    log.write_text("2024-03-01T10:00:00 INFO started\n2024-03-01T10:00:01 ERROR boom\n")
    out = tmp_path / "entries.csv"
    process_log(log, out).close()
    assert [e.source for e in import_csv(out)] == ["api.log", "api.log"]


# Brief: "when a run appends to such a file, the existing rows keep an empty source and the new
# rows carry theirs, and the file ends up in the new four-column format".
def test_append_to_old_format_file_upgrades_it(tmp_path):
    out = tmp_path / "entries.csv"
    out.write_text(OLD_FORMAT)
    log = tmp_path / "worker.log"
    log.write_text("2024-03-01T11:00:00 WARNING disk low\n")
    process_log(log, out).close()
    entries = import_csv(out)
    assert [(e.message, e.source) for e in entries] == [
        ("server started", ""),
        ("boom", ""),
        ("disk low", "worker.log"),
    ]
    with out.open(newline="") as f:
        header = next(csv.reader(f))
    assert header == ["timestamp", "level", "message", "source"]


# Brief: "Report summary gains `by_source` (source -> count) next to `by_level`" and "the
# report on [old files] must still work".
def test_report_by_source(tmp_path):
    out = tmp_path / "entries.csv"
    writer = EntryWriter(out)
    writer.write(LogEntry("2024-03-01T10:00:00", "INFO", "a", "api.log"))
    writer.write(LogEntry("2024-03-01T10:00:01", "INFO", "b", "api.log"))
    writer.write(LogEntry("2024-03-01T10:00:02", "ERROR", "c", "worker.log"))
    writer.close()
    summary = build_report(out)
    assert summary["by_level"] == {"INFO": 2, "ERROR": 1}
    assert summary["by_source"] == {"api.log": 2, "worker.log": 1}

    old = tmp_path / "old.csv"
    old.write_text(OLD_FORMAT)
    assert build_report(old)["by_source"] == {"": 2}


# Brief: the `process` command (the user-facing surface) still works end to end.
def test_cli_process_still_works(tmp_path, capsys):
    log = tmp_path / "app.log"
    log.write_text("2024-03-01T10:00:00 INFO started\n")
    out = tmp_path / "entries.csv"
    assert main(["process", str(log), "--out", str(out)]) == 0
    assert "1 entries" in capsys.readouterr().out
    assert import_csv(out)[0].source == "app.log"
