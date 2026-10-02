"""Hidden grader: size parsing (exp06 stratum C; keyed interpretation)."""

import pytest

from toolbelt.numbers import parse_size
from toolbelt.retention import load


@pytest.mark.parametrize("text,value", [
    ("500MB", 500 * 10**6), ("2GiB", 2 * 2**30), ("1KB", 1000), ("1KiB", 1024), ("3TB", 3 * 10**12),
    ("1TiB", 2**40), ("42", 42), ("42B", 42), ("1.5GB", 1_500_000_000), ("1.5KiB", 1536), (" 10 MB ", 10 * 10**6),
])
def test_parse_size(text, value):
    assert parse_size(text) == value


@pytest.mark.parametrize("bad", ["500 parsecs", "", "MB", "-1MB", "1.2.3GB"])
def test_garbage_rejected(bad):
    with pytest.raises(ValueError):
        parse_size(bad)


def test_retention_policy():
    assert load({"max_age_days": "7", "max_size": "500MB"}).max_size_bytes == 500_000_000
    assert load({"max_age_days": "7", "max_size": "2GiB"}).max_size_bytes == 2 * 2**30
    assert load({"max_age_days": "7"}).max_size_bytes is None
