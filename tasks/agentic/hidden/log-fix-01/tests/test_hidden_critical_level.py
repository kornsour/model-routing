from logproc.parser import parse_line


def test_critical_line_parses():
    entry = parse_line("2024-03-01T10:00:00 CRITICAL disk full")
    assert entry is not None
    assert entry.level == "CRITICAL"
    assert entry.message == "disk full"
