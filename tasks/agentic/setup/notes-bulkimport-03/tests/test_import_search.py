from notes.cli import main
from notes.export import HEADER
from notes.store import Store


def _csv(tmp_path, rows):
    path = tmp_path / "in.csv"
    path.write_text("\n".join([HEADER, *rows]) + "\n")
    return path


def test_search_finds_added_note(tmp_path, capsys):
    db = str(tmp_path / "notes.json")
    main(["--db", db, "add", "Buy oat milk"])
    main(["--db", db, "add", "Walk the dog"])
    capsys.readouterr()
    assert main(["--db", db, "search", "MILK"]) == 0
    assert capsys.readouterr().out == "#1 Buy oat milk\n"


def test_import_into_empty_store(tmp_path, capsys):
    db = str(tmp_path / "notes.json")
    path = _csv(tmp_path, ["7,Call the plumber,home,2024-03-01,False", "8,File taxes,,,False"])
    assert main(["--db", db, "import", str(path)]) == 0
    notes = Store(db).notes
    assert [(n.id, n.text, n.tags, n.due) for n in notes] == [
        (1, "Call the plumber", ["home"], "2024-03-01"),
        (2, "File taxes", [], None),
    ]
    capsys.readouterr()
    main(["--db", db, "search", "plumber"])
    assert capsys.readouterr().out == "#1 Call the plumber\n"


def test_index_built_for_store_without_one(tmp_path, capsys):
    db = tmp_path / "notes.json"
    db.write_text('[{"id": 4, "text": "Old note about taxes"}]')
    capsys.readouterr()
    main(["--db", str(db), "search", "taxes"])
    assert capsys.readouterr().out == "#4 Old note about taxes\n"
