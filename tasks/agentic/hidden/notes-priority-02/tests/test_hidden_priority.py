import json
import re

import pytest
from notes.cli import main
from notes.store import Store


def _rows(db):
    raw = json.loads(db.read_text())
    return raw if isinstance(raw, list) else raw["notes"]


def _list_lines(capsys):
    return [line for line in capsys.readouterr().out.splitlines() if line.startswith("[")]


# Brief: "`add` takes `--priority {low,normal,high}` (default normal) ... stored with the note"
def test_add_stores_priority_and_defaults_to_normal(tmp_path):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "Urgent thing", "--priority", "high"]) == 0
    assert main(["--db", str(db), "add", "Plain thing"]) == 0
    rows = _rows(db)
    assert rows[0]["priority"] == "high"
    assert rows[1]["priority"] == "normal"
    assert Store(db).notes[0].priority == "high"


# Brief: "`add --priority` with anything else is rejected"
def test_add_rejects_unknown_priority(tmp_path):
    db = tmp_path / "notes.json"
    with pytest.raises((SystemExit, ValueError)):
        main(["--db", str(db), "add", "x", "--priority", "urgent"])
    assert not db.exists() or _rows(db) == []


# Brief: "store files written by earlier versions (no priority) must keep loading, as normal"
def test_legacy_store_without_priority_loads_as_normal(tmp_path, capsys):
    db = tmp_path / "notes.json"
    db.write_text(json.dumps([{"id": 1, "text": "old", "tags": [], "due": None, "done": False}]))
    note = Store(db).notes[0]
    assert note.priority == "normal"
    assert main(["--db", str(db), "list"]) == 0
    assert _list_lines(capsys) == ["[ ] #1 old"]


# Brief: "`list` shows high-priority notes with `!` between the id and the text ... orders
# high before normal before low, ties by id"
def test_list_marks_high_and_orders_by_priority_then_id(tmp_path, capsys):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "low one", "--priority", "low"]) == 0
    assert main(["--db", str(db), "add", "normal one"]) == 0
    assert main(["--db", str(db), "add", "high one", "--priority", "high"]) == 0
    assert main(["--db", str(db), "add", "normal two", "--priority", "normal"]) == 0
    assert main(["--db", str(db), "add", "high two", "--priority", "high"]) == 0
    capsys.readouterr()
    assert main(["--db", str(db), "list"]) == 0
    assert _list_lines(capsys) == [
        "[ ] #3 ! high one",
        "[ ] #5 ! high two",
        "[ ] #2 normal one",
        "[ ] #4 normal two",
        "[ ] #1 low one",
    ]


# Brief: "`list --priority <level>` shows only notes at that level"
def test_list_filters_by_priority(tmp_path, capsys):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "a", "--priority", "high"]) == 0
    assert main(["--db", str(db), "add", "b"]) == 0
    assert main(["--db", str(db), "add", "c", "--priority", "high"]) == 0
    capsys.readouterr()
    assert main(["--db", str(db), "list", "--priority", "high"]) == 0
    assert re.findall(r"#\d+", "\n".join(_list_lines(capsys))) == ["#1", "#3"]
    assert main(["--db", str(db), "list", "--priority", "normal"]) == 0
    assert re.findall(r"#\d+", "\n".join(_list_lines(capsys))) == ["#2"]


# Brief: "priority round-trips through CSV export and `import` as a `priority` column
# after `done`"
def test_priority_round_trips_through_export_and_import(tmp_path):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "a", "--priority", "high"]) == 0
    assert main(["--db", str(db), "add", "b", "--priority", "low"]) == 0
    csv_path = tmp_path / "out.csv"
    assert main(["--db", str(db), "export", str(csv_path)]) == 0
    lines = csv_path.read_text().splitlines()
    assert lines[0] == "id,text,tags,due,done,priority"
    assert lines[1].split(",")[5] == "high"

    other = tmp_path / "other.json"
    assert main(["--db", str(other), "import", str(csv_path)]) == 0
    assert [(n.text, n.priority) for n in Store(other).notes] == [("a", "high"), ("b", "low")]


# Brief: "CSV files written by earlier versions (no priority column) must still import, as normal"
def test_legacy_csv_without_priority_column_imports_as_normal(tmp_path):
    db = tmp_path / "notes.json"
    csv_path = tmp_path / "old.csv"
    csv_path.write_text("id,text,tags,due,done\n1,Buy milk,errand,2024-03-01,False\n")
    assert main(["--db", str(db), "import", str(csv_path)]) == 0
    note = Store(db).notes[0]
    assert (note.text, note.tags, note.due, note.priority) == (
        "Buy milk",
        ["errand"],
        "2024-03-01",
        "normal",
    )
