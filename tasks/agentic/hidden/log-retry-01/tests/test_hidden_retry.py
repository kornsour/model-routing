from logproc.retry import RateLimited, push_summary


def test_retries_and_honors_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    calls = {"n": 0}

    def sender(summary):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimited(retry_after=3.0)

    assert push_summary({"count": 2}, sender) is True
    assert calls["n"] == 2
    assert sleeps == [3.0]


def test_gives_up_returns_false(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    def sender(summary):
        raise RateLimited(retry_after=0.1)

    assert push_summary({"count": 2}, sender, max_retries=2) is False
