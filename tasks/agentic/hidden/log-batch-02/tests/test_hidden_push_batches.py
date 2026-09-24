import time

import logproc.retry as retry_module
import pytest
from logproc.retry import RateLimited, push_batches

SUMMARIES = [{"n": i} for i in range(7)]  # batch_size=3 -> [0,1,2] [3,4,5] [6]
BATCHES = [SUMMARIES[0:3], SUMMARIES[3:6], SUMMARIES[6:7]]


class FakeRemote:
    """Rate-limits on the call numbers in ``limit_on`` (1-based); records the rest."""

    def __init__(self, limit_on=(), retry_after=1.5):
        self.limit_on = set(limit_on)
        self.retry_after = retry_after
        self.calls = 0
        self.recorded: list[list[dict]] = []

    def __call__(self, batch):
        self.calls += 1
        if self.calls in self.limit_on:
            raise RateLimited(self.retry_after)
        self.recorded.append(list(batch))


@pytest.fixture
def sleeps(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: calls.append(s))
    if hasattr(retry_module, "sleep"):
        monkeypatch.setattr(retry_module, "sleep", lambda s: calls.append(s))
    return calls


# Brief: "a batch the sender rejected with RateLimited must be retried after waiting exactly the
# retry_after it carries (via time.sleep)", and "every summary exactly once".
def test_rate_limited_batch_is_retried_not_resent(sleeps):
    remote = FakeRemote(limit_on={2}, retry_after=2.5)
    assert push_batches(SUMMARIES, remote, batch_size=3) == 7
    assert remote.recorded == BATCHES
    assert sleeps == [2.5]
    # Brief: "every sender call is either the first attempt at a batch or the retry after a
    # rate-limit response - no extra probes, no resends".
    assert remote.calls == 3 + 1


# Brief: same, with the very first call and a middle one limited twice in a row.
def test_consecutive_rate_limits_on_one_batch(sleeps):
    remote = FakeRemote(limit_on={1, 3, 4}, retry_after=0.5)
    assert push_batches(SUMMARIES, remote, batch_size=3) == 7
    assert remote.recorded == BATCHES
    assert remote.calls == 3 + 3
    assert sleeps == [0.5, 0.5, 0.5]


# Brief: "after max_retries consecutive rate-limits on the same batch the function gives up,
# stops there, returns the number of summaries delivered, and raises nothing".
def test_gives_up_after_max_retries_on_one_batch(sleeps):
    remote = FakeRemote(limit_on={2, 3, 4, 5, 6, 7, 8})
    delivered = push_batches(SUMMARIES, remote, batch_size=3, max_retries=2)
    assert delivered == 3
    assert remote.recorded == [BATCHES[0]]
    # one call for batch 1, then 1 + max_retries attempts on batch 2, nothing after.
    assert remote.calls == 1 + 3
    assert sleeps == [1.5, 1.5]


# Brief: "max_retries ... (default 3)".
def test_default_max_retries_is_three(sleeps):
    remote = FakeRemote(limit_on=set(range(1, 100)))
    assert push_batches(SUMMARIES, remote, batch_size=3) == 0
    assert remote.calls == 4
    assert remote.recorded == []


# Brief: "a success resets the count - only consecutive rate-limits on the same batch count".
def test_retry_budget_is_per_batch(sleeps):
    remote = FakeRemote(limit_on={1, 2, 4, 5, 7, 8})
    assert push_batches(SUMMARIES, remote, batch_size=3, max_retries=2) == 7
    assert remote.recorded == BATCHES
    assert remote.calls == 9


# Brief: "batches keep batch_size summaries each (the last may be shorter) and go in order";
# an empty run sends nothing.
def test_empty_input_sends_nothing(sleeps):
    remote = FakeRemote()
    assert push_batches([], remote, batch_size=3) == 0
    assert remote.calls == 0
    assert sleeps == []
