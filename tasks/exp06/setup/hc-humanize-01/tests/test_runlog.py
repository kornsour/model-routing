from datetime import UTC, datetime

from toolbelt.runlog import format_line


def test_line_prefix():
    line = format_line(datetime(2026, 9, 1, 2, tzinfo=UTC), "load", 1, "ok", 12.0)
    assert line.startswith("2026-09-01T02:00:00Z job=load attempt=1 status=ok took=")
