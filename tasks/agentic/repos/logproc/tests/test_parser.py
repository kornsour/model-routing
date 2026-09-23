from logproc.parser import parse_line


def test_parse_info_line():
    entry = parse_line("2024-03-01T10:00:00 INFO server started")
    assert entry is not None
    assert entry.level == "INFO"
    assert entry.message == "server started"


def test_parse_blank_line_is_none():
    assert parse_line("") is None


def test_parse_malformed_line_is_none():
    assert parse_line("not a log line") is None
