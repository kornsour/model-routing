import pytest

from toolbelt.backoff import Backoff


def test_exponential_with_cap():
    assert Backoff(1, cap=5).schedule(4) == [1, 2, 4, 5]


def test_jitter_needs_seed():
    with pytest.raises(ValueError):
        Backoff(1, jitter="full")
    b = Backoff(4, jitter="equal", seed=3)
    assert b.delay(2) == b.delay(2) and 4 <= b.delay(2) <= 8
