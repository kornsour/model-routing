from toolbelt.numbers import format_size
from toolbelt.retention import load


def test_max_age():
    assert load({"max_age_days": "30"}).max_age_days == 30


def test_format_size():
    assert format_size(1536) == "1.5 KiB"
    assert format_size(10) == "10 B"
