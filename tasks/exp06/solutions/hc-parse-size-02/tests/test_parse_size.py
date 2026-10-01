from toolbelt.numbers import parse_size
from toolbelt.retention import load


def test_si_and_iec():
    assert parse_size("1MB") == 1_000_000 and parse_size("1MiB") == 1_048_576


def test_policy_size():
    assert load({"max_age_days": "1", "max_size": "1KB"}).max_size_bytes == 1000
