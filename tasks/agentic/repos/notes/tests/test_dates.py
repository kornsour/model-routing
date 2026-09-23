from datetime import date

from notes.dates import parse_due


def test_parse_due_iso():
    assert parse_due("2024-03-01") == date(2024, 3, 1)


def test_parse_due_us():
    assert parse_due("03/01/2024") == date(2024, 3, 1)
