from notes.archive import archive_done
from notes.cli import main
from notes.store import Store


def test_archive_moves_the_done_note(tmp_path):
    db = tmp_path / "notes.json"
    store = Store(db)
    store.add("open one")
    store.add("finished")
    store.add("open two")
    store.mark_done(2)

    archive_done(store, tmp_path / "archive.json")

    assert [n.text for n in Store(db).notes] == ["open one", "open two"]
    assert [n.text for n in Store(tmp_path / "archive.json").notes] == ["finished"]


def test_archive_command_reports_count(tmp_path, capsys):
    db = tmp_path / "notes.json"
    store = Store(db)
    store.add("finished")
    store.mark_done(1)
    assert main(["--db", str(db), "archive"]) == 0
    assert "archived 1 notes" in capsys.readouterr().out
