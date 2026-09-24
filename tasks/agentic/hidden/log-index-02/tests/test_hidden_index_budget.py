import builtins
import io
from datetime import datetime
from pathlib import Path

import pytest
from logproc.csvexport import export_csv
from logproc.index import EntryIndex
from logproc.parser import LogEntry
from logproc.pipeline import EntryWriter

ENTRIES = [
    LogEntry("2024-03-01T10:00:00", "INFO", "started"),
    LogEntry("2024-03-01T10:00:05", "ERROR", "boom"),
    LogEntry("2024-03-01T10:00:09", "INFO", "recovered"),
    LogEntry("2024-03-01T10:00:12", "WARNING", "disk low"),
]


@pytest.fixture
def open_counter(monkeypatch):
    """Count every read-open of a given path, whichever API is used to read it."""
    calls: list[str] = []
    real_open = io.open

    def counting_open(file, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if not any(flag in mode for flag in "wax"):  # count reads only, not the test's writes
            calls.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", counting_open)
    monkeypatch.setattr(builtins, "open", counting_open)

    def opens_of(path) -> int:
        return sum(1 for c in calls if c == str(path))

    return opens_of


def _mixed_queries(index: EntryIndex) -> tuple:
    return (
        index.count(),
        index.count("INFO"),
        index.levels(),
        [e.message for e in index.entries_for("ERROR")],
        [
            e.message
            for e in index.between(datetime(2024, 3, 1, 10, 0, 3), datetime(2024, 3, 1, 10, 0, 10))
        ],
        index.count("WARNING"),
    )


EXPECTED = (4, 2, ["ERROR", "INFO", "WARNING"], ["boom"], ["boom", "recovered"], 1)


# Brief: "any sequence of queries on an index, whatever mix of methods, must read the CSV from
# disk at most once until `refresh()` is called".
def test_mixed_queries_read_disk_at_most_once(tmp_path, open_counter):
    path = tmp_path / "entries.csv"
    export_csv(ENTRIES, path)
    index = EntryIndex(path)
    assert _mixed_queries(index) == EXPECTED
    assert _mixed_queries(index) == EXPECTED
    assert open_counter(path) <= 1


# Brief: "after `refresh()` the next query must see rows flushed since" and the re-read costs
# "at most one more read".
def test_refresh_picks_up_new_rows_with_one_more_read(tmp_path, open_counter):
    path = tmp_path / "entries.csv"
    export_csv(ENTRIES, path)
    index = EntryIndex(path)
    assert index.count() == 4
    writer = EntryWriter(path)
    writer.write(LogEntry("2024-03-01T10:00:20", "ERROR", "again"))
    writer.close()
    assert index.count() == 4  # still the snapshot: nothing asked for a refresh
    before = open_counter(path)
    index.refresh()
    assert index.count("ERROR") == 2
    assert [e.message for e in index.entries_for("ERROR")] == ["boom", "again"]
    assert index.levels() == ["ERROR", "INFO", "WARNING"]
    assert open_counter(path) - before <= 1


# Brief: "an index may be created before its CSV exists" - it answers empty, and once the file
# appears a `refresh()` makes it visible.
def test_index_created_before_csv_exists(tmp_path):
    path = Path(tmp_path) / "entries.csv"
    index = EntryIndex(path)
    assert index.count() == 0
    assert index.levels() == []
    assert index.entries_for("INFO") == []
    export_csv(ENTRIES, path)
    index.refresh()
    assert index.count() == 4
    assert index.count("INFO") == 2


# Brief: "the index is a read-only view: it never writes the CSV" - querying and refreshing
# must leave the file byte-for-byte unchanged.
def test_index_never_writes_csv(tmp_path):
    path = tmp_path / "entries.csv"
    export_csv(ENTRIES, path)
    original = path.read_bytes()
    index = EntryIndex(path)
    _mixed_queries(index)
    index.refresh()
    _mixed_queries(index)
    assert path.read_bytes() == original
