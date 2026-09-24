from logproc.timestamps import parse_timestamp


def _fields(parsed):
    return (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second)


def test_parse_timestamp_iso():
    assert _fields(parse_timestamp("2024-03-01T10:00:00")) == (2024, 3, 1, 10, 0, 0)


def test_parse_timestamp_spaced():
    assert _fields(parse_timestamp("2024-03-01 10:00:00")) == (2024, 3, 1, 10, 0, 0)
