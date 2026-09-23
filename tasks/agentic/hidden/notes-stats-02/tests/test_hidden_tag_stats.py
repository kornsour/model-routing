import json

from notes.cli import main
from notes.store import Store

LEGACY = [
    {"id": 1, "text": "Pay rent", "tags": ["Errand", "errand"], "due": None, "done": False},
    {"id": 2, "text": "Buy milk", "tags": ["errand"], "due": None, "done": False},
    {"id": 3, "text": "Fix sink", "tags": ["ERRAND", "home"], "due": None, "done": True},
    {"id": 4, "text": "Call mum", "tags": ["Home"], "due": None, "done": False},
]


def _legacy_db(tmp_path):
    db = tmp_path / "notes.json"
    db.write_text(json.dumps(LEGACY, indent=2))
    return db


def _tag_lines(out):
    return [line.strip() for line in out.splitlines() if line.startswith("  ")]


# Brief: "notes already saved with mixed-case or duplicated tags must count correctly ...
# a note contributes at most once per tag ... `stats` lists tags in lowercase"
def test_stats_counts_notes_once_per_tag_case_insensitively(tmp_path, capsys):
    db = _legacy_db(tmp_path)
    assert main(["--db", str(db), "stats"]) == 0
    lines = _tag_lines(capsys.readouterr().out)
    assert lines == ["errand: 3", "home: 2"]


# Brief: "for every tag, the count `stats` reports equals the number of notes
# `notes tag <tag>` lists, however the tag was capitalized at entry or in the query"
def test_tag_filter_matches_case_insensitively_on_stored_data(tmp_path, capsys):
    db = _legacy_db(tmp_path)
    for query in ("errand", "ERRAND", "Errand"):
        assert main(["--db", str(db), "tag", query]) == 0
        ids = [line.split()[0] for line in capsys.readouterr().out.splitlines()]
        assert ids == ["#1", "#2", "#3"], f"query {query!r} gave {ids}"
    assert main(["--db", str(db), "tag", "home"]) == 0
    ids = [line.split()[0] for line in capsys.readouterr().out.splitlines()]
    assert ids == ["#3", "#4"]


# Brief: "a note never carries the same tag twice" (tags entered as `Errand, errand`)
def test_add_does_not_store_duplicate_tags(tmp_path, capsys):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "Pay rent", "--tag", "Errand, errand"]) == 0
    note = Store(db).notes[0]
    assert len(note.tags) == 1
    assert note.tags[0].lower() == "errand"
    capsys.readouterr()
    assert main(["--db", str(db), "stats"]) == 0
    assert _tag_lines(capsys.readouterr().out) == ["errand: 1"]


# Brief: "`stats` lists tags ... most common first, ties alphabetically"
def test_stats_orders_by_count_then_name(tmp_path, capsys):
    db = tmp_path / "notes.json"
    rows = [
        {"id": 1, "text": "a", "tags": ["Work", "zeta"], "due": None, "done": False},
        {"id": 2, "text": "b", "tags": ["work", "Alpha"], "due": None, "done": False},
        {"id": 3, "text": "c", "tags": ["alpha"], "due": None, "done": False},
    ]
    db.write_text(json.dumps(rows))
    assert main(["--db", str(db), "stats"]) == 0
    assert _tag_lines(capsys.readouterr().out) == ["alpha: 2", "work: 2", "zeta: 1"]
