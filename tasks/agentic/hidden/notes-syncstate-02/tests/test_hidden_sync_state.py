import pytest
from notes.models import Note
from notes.sync import RateLimited, sync_changed


class Recorder:
    def __init__(self, failures=None):
        self.calls: list[int] = []
        self.failures = dict(failures or {})

    def __call__(self, note):
        self.calls.append(note.id)
        fail = self.failures.get(note.id)
        if fail is not None:
            if isinstance(fail, int):
                self.failures[note.id] = fail - 1 if fail > 1 else None
                raise RateLimited(2.5)
            raise fail


def _notes():
    return [Note(id=1, text="a"), Note(id=2, text="b"), Note(id=3, text="c")]


# Brief: "each run pushes exactly the notes that were added or changed (any field) since
# they were last successfully pushed"
def test_changed_note_is_pushed_again(tmp_path):
    state = tmp_path / "sync.json"
    notes = _notes()
    assert sync_changed(notes, Recorder(), state) == [1, 2, 3]

    notes[1].done = True
    second = Recorder()
    assert sync_changed(notes, second, state) == [2]
    assert second.calls == [2]

    notes[0].tags = ["urgent"]
    third = Recorder()
    assert sync_changed(notes, third, state) == [1]


# Brief: "an unchanged note is never re-sent, and a second run right after a successful
# one pushes nothing"
def test_unchanged_notes_are_not_resent(tmp_path):
    state = tmp_path / "sync.json"
    notes = _notes()
    sync_changed(notes, Recorder(), state)
    again = Recorder()
    assert sync_changed(notes, again, state) == []
    assert again.calls == []


# Brief: "a `RateLimited` ... is retried for that note after waiting exactly `retry_after`
# (via `time.sleep`)"
def test_rate_limited_note_is_retried_after_retry_after(tmp_path, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    state = tmp_path / "sync.json"
    pusher = Recorder(failures={2: 1})

    assert sync_changed(_notes(), pusher, state) == [1, 2, 3]
    assert sleeps == [2.5]
    assert pusher.calls == [1, 2, 2, 3]


# Brief: "a note still rate-limited after `max_retries` attempts is skipped, the rest of
# the batch continues, and that note is pushed again on the next run"
def test_persistently_rate_limited_note_is_skipped_then_retried_next_run(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    state = tmp_path / "sync.json"
    stubborn = Recorder(failures={2: 99})

    assert sync_changed(_notes(), stubborn, state, max_retries=3) == [1, 3]
    assert stubborn.calls.count(2) == 3

    healed = Recorder()
    assert sync_changed(_notes(), healed, state) == [2]
    assert healed.calls == [2]


# Brief: "if the pusher raises anything else, let it propagate, but what was pushed before
# it must already be recorded (not re-sent next run)"
def test_progress_survives_a_hard_failure(tmp_path):
    state = tmp_path / "sync.json"
    crashing = Recorder(failures={3: RuntimeError("remote exploded")})

    with pytest.raises(RuntimeError):
        sync_changed(_notes(), crashing, state)

    retry = Recorder()
    assert sync_changed(_notes(), retry, state) == [3]
    assert retry.calls == [3]
