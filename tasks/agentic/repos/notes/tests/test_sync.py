from notes.models import Note
from notes.sync import push_all


def test_push_all_success():
    pushed = []

    def pusher(note):
        pushed.append(note.id)

    notes = [Note(id=1, text="a"), Note(id=2, text="b")]
    result = push_all(notes, pusher)
    assert result == [1, 2]
    assert pushed == [1, 2]
