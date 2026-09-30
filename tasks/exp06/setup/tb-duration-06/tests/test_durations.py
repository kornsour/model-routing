from datetime import datetime

from toolbelt.durations import Duration, add, parse_duration


def test_parse():
    assert parse_duration("P1DT2H") == Duration(days=1, hours=2)
    assert str(parse_duration("PT90M")) == "PT90M"


def test_add_simple():
    assert add(datetime(2026, 3, 1, 12), parse_duration("PT6H")) == datetime(2026, 3, 1, 18)
    assert add(datetime(2026, 3, 1), parse_duration("P2D")) == datetime(2026, 3, 3)
