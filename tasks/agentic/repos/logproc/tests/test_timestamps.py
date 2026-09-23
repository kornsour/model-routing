from datetime import datetime

from logproc.timestamps import parse_timestamp


def test_parse_timestamp_iso():
    assert parse_timestamp("2024-03-01T10:00:00") == datetime(2024, 3, 1, 10, 0, 0)


def test_parse_timestamp_spaced():
    assert parse_timestamp("2024-03-01 10:00:00") == datetime(2024, 3, 1, 10, 0, 0)
