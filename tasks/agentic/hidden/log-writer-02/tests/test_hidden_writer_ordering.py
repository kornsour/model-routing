from logproc.cli import main
from logproc.csvexport import import_csv
from logproc.parser import LogEntry
from logproc.pipeline import EntryWriter, build_report, process_log, process_logs


def _logs(tmp_path):
    a = tmp_path / "a.log"
    b = tmp_path / "b.log"
    c = tmp_path / "c.log"
    a.write_text("2024-03-01T10:00:00 INFO a1\n2024-03-01T10:00:01 INFO a2\n")
    b.write_text("2024-03-01T10:00:02 ERROR b1\n")
    c.write_text("2024-03-01T10:00:03 WARNING c1\n2024-03-01T10:00:04 INFO c2\n")
    return [a, b, c]


# Brief: "`process_logs` ... must end up with every entry from every file, in the order the
# files were given and in line order within a file, each exactly once".
def test_process_logs_keeps_every_file_in_order(tmp_path):
    out = tmp_path / "entries.csv"
    process_logs(_logs(tmp_path), out).close()
    assert [e.message for e in import_csv(out)] == ["a1", "a2", "b1", "c1", "c2"]
    assert build_report(out)["count"] == 5


# Brief: "`logproc process a.log b.log c.log` only reports the last file's entries" is the
# symptom; the CLI must report all of them.
def test_cli_process_many_files(tmp_path, capsys):
    out = tmp_path / "entries.csv"
    logs = [str(p) for p in _logs(tmp_path)]
    assert main(["process", *logs, "--out", str(out)]) == 0
    assert "5 entries" in capsys.readouterr().out


# Brief: "a second close of the same writer must leave the file exactly as the first left it".
def test_close_is_idempotent(tmp_path):
    out = tmp_path / "entries.csv"
    writer = process_log(_logs(tmp_path)[0], out)
    writer.close()
    first = out.read_bytes()
    writer.close()
    assert out.read_bytes() == first
    assert build_report(out)["count"] == 2


# Brief / module docstring: "whatever is already in the CSV when a writer flushes - rows from an
# earlier run, or rows another writer flushed to the same file a moment before - is kept".
def test_writer_keeps_rows_flushed_by_another_writer_after_it_was_created(tmp_path):
    out = tmp_path / "entries.csv"
    a, b, _ = _logs(tmp_path)
    first = process_log(a, out)
    second = process_log(b, out)  # created before `first` has flushed anything
    first.close()
    second.close()
    assert [e.message for e in import_csv(out)] == ["a1", "a2", "b1"]


# Brief: "rows from an earlier run" are kept - a later run appends after them.
def test_later_run_appends_after_earlier_run(tmp_path):
    out = tmp_path / "entries.csv"
    a, b, c = _logs(tmp_path)
    process_logs([a], out).close()
    process_logs([b, c], out).close()
    assert [e.message for e in import_csv(out)] == ["a1", "a2", "b1", "c1", "c2"]


# Brief: idempotent close must also hold when more is written between closes - only the new
# rows are added, nothing is written twice.
def test_write_after_close_adds_only_new_rows(tmp_path):
    out = tmp_path / "entries.csv"
    writer = EntryWriter(out)
    writer.write(LogEntry("2024-03-01T10:00:00", "INFO", "one"))
    writer.close()
    writer.write(LogEntry("2024-03-01T10:00:01", "INFO", "two"))
    writer.close()
    writer.close()
    assert [e.message for e in import_csv(out)] == ["one", "two"]
