import json

from notes.cli import main
from notes.store import Store


# Brief: "after deleting any note(s), including the highest, a subsequent add gets an id
# higher than any the file has ever handed out"
def test_delete_highest_then_add_does_not_reuse_id(tmp_path):
    store = Store(tmp_path / "notes.json")
    store.add("a")
    doomed = store.add("b")
    assert store.remove(doomed.id)
    assert store.add("c").id > doomed.id


# Brief: "this holds across separate CLI invocations (every command opens the store afresh)"
def test_ids_are_not_reused_across_cli_invocations(tmp_path, capsys):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "a"]) == 0
    assert main(["--db", str(db), "add", "b"]) == 0
    assert main(["--db", str(db), "delete", "2"]) == 0
    assert main(["--db", str(db), "add", "c"]) == 0
    assert "added note #3" in capsys.readouterr().out
    assert [(n.id, n.text) for n in Store(db).notes] == [(1, "a"), (3, "c")]


# Brief: "after deleting any note(s) ... a subsequent add gets an id higher than any the
# file has ever handed out" (even when the store is emptied first)
def test_deleting_every_note_keeps_counting(tmp_path):
    db = tmp_path / "notes.json"
    store = Store(db)
    store.add("a")
    store.add("b")
    store.remove(1)
    store.remove(2)
    assert Store(db).add("c").id == 3


# Brief: "and for notes brought in by `import`"
def test_imported_ids_are_never_reused(tmp_path, capsys):
    db = tmp_path / "notes.json"
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("id,text,tags,due,done\n7,x,,,False\n8,y,,,False\n")
    assert main(["--db", str(db), "import", str(csv_path)]) == 0
    highest = max(n.id for n in Store(db).notes)
    assert main(["--db", str(db), "delete", str(highest)]) == 0
    assert main(["--db", str(db), "add", "z"]) == 0
    assert Store(db).notes[-1].id > highest


# Brief: "files written by earlier versions must keep loading, keep every note, and
# continue numbering above their highest id"
def test_legacy_list_format_loads_and_continues_numbering(tmp_path):
    db = tmp_path / "notes.json"
    legacy = [
        {"id": 1, "text": "a", "tags": [], "due": None, "done": False},
        {"id": 5, "text": "b", "tags": ["x"], "due": "2024-03-01", "done": True},
    ]
    db.write_text(json.dumps(legacy, indent=2))
    store = Store(db)
    assert [(n.id, n.text, n.tags, n.due, n.done) for n in store.notes] == [
        (1, "a", [], None, False),
        (5, "b", ["x"], "2024-03-01", True),
    ]
    assert store.add("c").id == 6
    assert [n.id for n in Store(db).notes] == [1, 5, 6]
