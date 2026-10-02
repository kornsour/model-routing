"""Hidden grader: legacy-compatible durations (exp06 stratum C; keyed interpretation)."""

import re
from datetime import UTC, datetime

import pytest

from toolbelt.runlog import format_line, humanize


@pytest.mark.parametrize("seconds,text", [
    (7384.2, "2h 3m"), (45, "45s"), (60, "1m 0s"), (0, "0s"), (0.9, "0s"), (86400, "1d 0h"),
    (14399.9, "3h 59m"), (90061, "1d 1h"), (3600, "1h 0m"), (59.99, "59s"), (3 * 86400 + 59, "3d 0h"),
])
def test_humanize(seconds, text):
    assert humanize(seconds) == text


def test_negative_rejected():
    with pytest.raises(ValueError):
        humanize(-1)


def test_line_matches_shipper_pattern():
    line = format_line(datetime(2026, 9, 1, 2, 14, 7, tzinfo=UTC), "load_orders", 1, "ok", 7384.2)
    assert line == "2026-09-01T02:14:07Z job=load_orders attempt=1 status=ok took=2h 3m"
    took = line.split("took=", 1)[1]
    assert re.fullmatch(r"(\d+[dhms])( \d+[dhms])?", took)
