import json
import re

from notes.cli import main
from notes.store import Store

LEGACY = [
    {"id": 1, "text": "Pay rent", "tags": [], "due": "03/01/2024", "done": False},
    {"id": 2, "text": "Dentist", "tags": [], "due": "2024-02-01", "done": False},
    {"id": 3, "text": "No date", "tags": [], "due": None, "done": False},
]


def _legacy_db(tmp_path):
    db = tmp_path / "notes.json"
    db.write_text(json.dumps(LEGACY, indent=2))
    return db


def _rows(db):
    raw = json.loads(db.read_text())
    return raw if isinstance(raw, list) else raw["notes"]


# Brief: "`add` ... in either accepted format ... stored in the canonical ISO form"
def test_add_us_format_is_stored_as_iso(tmp_path):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "Pay rent", "--due", "03/01/2024"]) == 0
    assert _rows(db)[0]["due"] == "2024-03-01"


# Brief: "stores written by earlier versions ... must keep loading and behave exactly as if
# the date had been entered in ISO form, including after a save"
def test_legacy_store_loads_canonical_and_saves_iso(tmp_path):
    db = _legacy_db(tmp_path)
    store = Store(db)
    assert [n.due for n in store.notes] == ["2024-03-01", "2024-02-01", None]
    store.save()
    assert [r["due"] for r in _rows(db)] == ["2024-03-01", "2024-02-01", None]


# Brief: "`list --due-before` ... compare by calendar date regardless of how the date was entered"
def test_due_before_uses_calendar_order(tmp_path, capsys):
    db = _legacy_db(tmp_path)
    assert main(["--db", str(db), "list", "--due-before", "2024-02-15"]) == 0
    out = capsys.readouterr().out
    assert "#2" in out
    assert "#1" not in out
    assert "#3" not in out


# Brief: "`--sort-due` ... sort by calendar date regardless of how the date was entered"
def test_sort_due_uses_calendar_order(tmp_path, capsys):
    db = _legacy_db(tmp_path)
    assert main(["--db", str(db), "list", "--sort-due"]) == 0
    ids = re.findall(r"#\d+", capsys.readouterr().out)
    assert ids == ["#2", "#1", "#3"]


# Brief: "CSV export ... must emit the ISO form"
def test_export_emits_iso(tmp_path):
    db = _legacy_db(tmp_path)
    csv_path = tmp_path / "out.csv"
    assert main(["--db", str(db), "export", str(csv_path)]) == 0
    lines = csv_path.read_text().splitlines()
    assert lines[1].split(",")[3] == "2024-03-01"
    assert lines[2].split(",")[3] == "2024-02-01"


# Brief: "`import` (in either accepted format) ... stored in the canonical ISO form"
def test_import_us_format_is_stored_as_iso(tmp_path):
    db = tmp_path / "notes.json"
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("id,text,tags,due,done\n1,Pay rent,,03/01/2024,False\n")
    assert main(["--db", str(db), "import", str(csv_path)]) == 0
    assert _rows(db)[0]["due"] == "2024-03-01"
