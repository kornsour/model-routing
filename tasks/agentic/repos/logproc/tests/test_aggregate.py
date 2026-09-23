from logproc.aggregate import count_by_level, paginate
from logproc.parser import LogEntry


def _entries(n):
    return [LogEntry(timestamp=f"t{i}", level="INFO", message=f"m{i}") for i in range(n)]


def test_count_by_level():
    entries = [
        LogEntry("t1", "INFO", "a"),
        LogEntry("t2", "ERROR", "b"),
        LogEntry("t3", "INFO", "c"),
    ]
    assert count_by_level(entries) == {"INFO": 2, "ERROR": 1}


def test_paginate_single_page():
    entries = _entries(3)
    assert paginate(entries, page=1, page_size=10) == entries
