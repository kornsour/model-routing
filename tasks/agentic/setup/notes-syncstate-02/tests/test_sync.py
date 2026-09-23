from notes.cli import main
from notes.models import Note
from notes.sync import push_all, sync_changed


def test_push_all_success():
    pushed = []

    def pusher(note):
        pushed.append(note.id)

    notes = [Note(id=1, text="a"), Note(id=2, text="b")]
    result = push_all(notes, pusher)
    assert result == [1, 2]
    assert pushed == [1, 2]


def test_sync_changed_pushes_new_notes_only(tmp_path):
    pushed = []
    state = tmp_path / "sync.json"
    notes = [Note(id=1, text="a"), Note(id=2, text="b")]

    assert sync_changed(notes, lambda n: pushed.append(n.id), state) == [1, 2]
    notes.append(Note(id=3, text="c"))
    assert sync_changed(notes, lambda n: pushed.append(n.id), state) == [3]
    assert pushed == [1, 2, 3]


def test_sync_command(tmp_path, capsys):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "Buy milk"]) == 0
    assert main(["--db", str(db), "sync"]) == 0
    assert "pushed 1 notes" in capsys.readouterr().out
    assert (tmp_path / "notes.json.remote.jsonl").read_text().count("\n") == 1
