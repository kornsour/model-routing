from notes.models import Note
from notes.sync import RateLimited, push_all


def test_retries_and_honors_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    calls = {1: 0}

    def pusher(note):
        calls[note.id] += 1
        if note.id == 1 and calls[note.id] == 1:
            raise RateLimited(retry_after=1.5)

    notes = [Note(id=1, text="a")]
    result = push_all(notes, pusher)

    assert result == [1]
    assert calls[1] == 2
    assert sleeps == [1.5]


def test_gives_up_after_max_retries_and_continues_batch(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    def pusher(note):
        if note.id == 1:
            raise RateLimited(retry_after=0.1)

    notes = [Note(id=1, text="a"), Note(id=2, text="b")]
    result = push_all(notes, pusher, max_retries=3)

    assert 1 not in result
    assert 2 in result
