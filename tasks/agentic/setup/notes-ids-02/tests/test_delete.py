from notes.cli import main
from notes.store import Store


def test_remove_drops_the_note(tmp_path):
    store = Store(tmp_path / "notes.json")
    store.add("Buy milk")
    store.add("Walk the dog")
    assert store.remove(1) is True
    assert [n.text for n in Store(store.path).notes] == ["Walk the dog"]
    assert store.remove(1) is False


def test_delete_command(tmp_path, capsys):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "Buy milk"]) == 0
    assert main(["--db", str(db), "delete", "1"]) == 0
    assert "deleted #1" in capsys.readouterr().out
    assert Store(db).notes == []
