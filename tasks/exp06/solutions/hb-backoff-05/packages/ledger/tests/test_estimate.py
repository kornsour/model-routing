import pytest

from orchestra import JobSpec

from ledger.estimate import estimate


def test_no_failures_is_one_attempt():
    e = estimate(JobSpec("a", duration=4, max_attempts=3, backoff=1, resources={"api": 1}), {"api": 0.5}, 0)
    assert (e.cost, e.seconds) == (pytest.approx(2.0), pytest.approx(4.0))
