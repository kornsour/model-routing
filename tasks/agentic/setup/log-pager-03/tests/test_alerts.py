from logproc.alerts import page_errors
from logproc.parser import LogEntry


def test_single_error_pages_once():
    pages = []
    entries = [
        LogEntry("2024-03-01T10:00:00", "INFO", "started"),
        LogEntry("2024-03-01T10:00:01", "ERROR", "db down"),
    ]
    assert page_errors(entries, pages.append) == 1
    assert pages == [
        {
            "timestamp": "2024-03-01T10:00:01",
            "level": "ERROR",
            "message": "db down",
            "suppressed": 0,
            "digest": False,
        }
    ]
