from notes.cli import main
from notes.store import Store


def test_done_command_marks_note_complete(tmp_path):
    db = tmp_path / "notes.json"
    store = Store(db)
    note = store.add("Buy milk")

    rc = main(["--db", str(db), "done", str(note.id)])
    assert rc == 0

    reloaded = Store(db)
    assert reloaded.get(note.id).done is True
