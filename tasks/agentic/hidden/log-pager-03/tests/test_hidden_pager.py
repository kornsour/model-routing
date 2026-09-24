from datetime import datetime, timedelta

from logproc.alerts import page_errors
from logproc.parser import LogEntry

T0 = datetime(2024, 3, 1, 0, 3, 0)


def _e(seconds, level, message):
    return LogEntry((T0 + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S"), level, message)


def _run(entries, window_seconds=600):
    pages = []
    sent = page_errors(entries, pages.append, window_seconds=window_seconds)
    # Contract: "Returns the number of pages sent. Nothing else ever calls ``sender``."
    assert sent == len(pages)
    return pages


# Brief symptom 1 (one problem whose message only differed in its numbers paged thousands of
# times); docstring: "every run of consecutive digits replaced by a single ``#``".
def test_numbers_of_any_length_are_one_problem():
    entries = [
        _e(i, "ERROR", f"timeout after {7 * i**3 + 5} ms on shard {i % 13}") for i in range(50)
    ]
    pages = _run(entries)
    assert len(pages) == 2
    assert pages[0]["message"] == entries[0].message
    assert pages[0]["suppressed"] == 0
    assert pages[0]["digest"] is False
    assert pages[1]["digest"] is True
    assert pages[1]["suppressed"] == 49
    assert pages[1]["message"] == entries[-1].message
    assert pages[1]["timestamp"] == entries[-1].timestamp


# Brief symptom 2 (an error firing every minute all night paged exactly once); docstring: the
# paging entry opens a window, the first entry at or after its end pages again, and
# ``suppressed`` counts entries since the signature's previous page.
def test_steady_error_repages_every_window_with_counts():
    entries = [_e(60 * i, "ERROR", "disk full on /var") for i in range(120)]
    pages = _run(entries)
    regular = [p for p in pages if not p["digest"]]
    assert [p["timestamp"] for p in regular] == [entries[i].timestamp for i in range(0, 120, 10)]
    assert [p["suppressed"] for p in regular] == [0] + [9] * 11
    digests = [p for p in pages if p["digest"]]
    assert len(digests) == 1
    assert digests[0]["suppressed"] == 9
    assert digests[0]["timestamp"] == entries[119].timestamp
    assert len(pages) == 13


# Docstring: "The first one at or after the window's end pages again"; suppressions already
# reported by a page get no digest.
def test_window_boundary_and_no_digest_when_everything_was_reported():
    entries = [
        _e(0, "ERROR", "db down"),
        _e(60, "ERROR", "db down"),
        _e(600, "ERROR", "db down"),
    ]
    pages = _run(entries)
    assert [(p["timestamp"], p["suppressed"], p["digest"]) for p in pages] == [
        (entries[0].timestamp, 0, False),
        (entries[2].timestamp, 1, False),
    ]


# Docstring: final digests go "in the order the signatures first paged".
def test_digests_in_order_of_first_page():
    entries = [
        _e(0, "ERROR", "db down"),
        _e(1, "ERROR", "cache down"),
        _e(2, "ERROR", "cache down"),
        _e(3, "ERROR", "db down"),
        _e(4, "ERROR", "db down"),
    ]
    pages = _run(entries)
    digests = [(p["message"], p["suppressed"]) for p in pages if p["digest"]]
    assert digests == [("db down", 2), ("cache down", 1)]
    assert len(pages) == 4


# Docstring: only ERROR and CRITICAL page; the level is part of the signature.
def test_levels():
    entries = [
        _e(0, "WARNING", "db slow"),
        _e(1, "INFO", "db slow"),
        _e(2, "ERROR", "db down 3"),
        _e(3, "CRITICAL", "db down 4"),
        _e(4, "ERROR", "db down 55"),
    ]
    pages = _run(entries)
    assert [(p["level"], p["message"], p["digest"]) for p in pages] == [
        ("ERROR", "db down 3", False),
        ("CRITICAL", "db down 4", False),
        ("ERROR", "db down 55", True),
    ]
