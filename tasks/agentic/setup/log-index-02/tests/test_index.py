from datetime import datetime

from logproc.csvexport import export_csv
from logproc.index import EntryIndex
from logproc.parser import LogEntry


def _write(path):
    export_csv(
        [
            LogEntry("2024-03-01T10:00:00", "INFO", "started"),
            LogEntry("2024-03-01T10:00:05", "ERROR", "boom"),
            LogEntry("2024-03-01T10:00:09", "INFO", "recovered"),
        ],
        path,
    )


def test_index_counts_and_levels(tmp_path):
    path = tmp_path / "entries.csv"
    _write(path)
    index = EntryIndex(path)
    assert index.count() == 3
    assert index.count("INFO") == 2
    assert index.levels() == ["ERROR", "INFO"]
    assert [e.message for e in index.entries_for("ERROR")] == ["boom"]


def test_index_between(tmp_path):
    path = tmp_path / "entries.csv"
    _write(path)
    index = EntryIndex(path)
    window = index.between(datetime(2024, 3, 1, 10, 0, 3), datetime(2024, 3, 1, 10, 0, 9))
    assert [e.message for e in window] == ["boom"]
