import builtins
import io
import os
from collections import Counter

from notes.cli import main
from notes.export import HEADER
from notes.store import Store


def _csv(tmp_path, rows, name="in.csv"):
    path = tmp_path / name
    path.write_text("\n".join([HEADER, *rows]) + "\n")
    return path


def _count_writes(monkeypatch, root):
    """Count, per file under ``root``, every open for writing and every rename onto it."""
    counts = Counter()
    real_open = io.open
    real_replace, real_rename = os.replace, os.rename
    root = str(root)

    def _note(target):
        target = os.path.realpath(os.fspath(target))
        if target.startswith(os.path.realpath(root)):
            counts[os.path.basename(target)] += 1

    def counting_open(file, mode="r", *args, **kwargs):
        if isinstance(file, (str, os.PathLike)) and any(c in mode for c in "wax+"):
            _note(file)
        return real_open(file, mode, *args, **kwargs)

    def counting_replace(src, dst, *args, **kwargs):
        _note(dst)
        return real_replace(src, dst, *args, **kwargs)

    def counting_rename(src, dst, *args, **kwargs):
        _note(dst)
        return real_rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(io, "open", counting_open)
    monkeypatch.setattr(builtins, "open", counting_open)
    monkeypatch.setattr(os, "replace", counting_replace)
    monkeypatch.setattr(os, "rename", counting_rename)
    return counts


def _rows(n):
    return [f"{i},Imported task number {i} about widget{i},bulk,2024-03-01,False" for i in range(n)]


def _search(capsys, db, query):
    capsys.readouterr()
    assert main(["--db", str(db), "search", query]) == 0
    return capsys.readouterr().out


# Brief: "`notes import` must write each file the tool keeps for a store - the store file and
# its search index - at most once per import, however many rows the CSV has"
def test_import_writes_each_file_at_most_once(tmp_path, monkeypatch):
    db = tmp_path / "notes.json"
    Store(db).add("existing note")
    path = _csv(tmp_path, _rows(60))
    counts = _count_writes(monkeypatch, tmp_path)
    assert main(["--db", str(db), "import", str(path)]) == 0
    monkeypatch.undo()
    assert counts, "import wrote nothing"
    too_many = {name: n for name, n in counts.items() if n > 1}
    assert not too_many, f"files written more than once: {too_many}"
    assert len(Store(db).notes) == 61


# Brief: "imported notes get fresh ids after the ones already in the store, in CSV order, and
# are findable with `notes search` straight away, exactly like notes created with `add`"
def test_imported_notes_are_numbered_and_searchable(tmp_path, capsys):
    db = tmp_path / "notes.json"
    Store(db).add("Buy oat milk")
    Store(db).add("Walk the dog")
    path = _csv(tmp_path, _rows(30))
    assert main(["--db", str(db), "import", str(path)]) == 0
    notes = Store(db).notes
    assert [n.id for n in notes] == list(range(1, 33))
    assert notes[2].text == "Imported task number 0 about widget0"
    assert notes[2].tags == ["bulk"]
    assert notes[2].due == "2024-03-01"
    assert _search(capsys, db, "widget17") == "#20 Imported task number 17 about widget17\n"
    assert _search(capsys, db, "milk") == "#1 Buy oat milk\n"
    assert _search(capsys, db, "imported task").count("\n") == 30
    main(["--db", str(db), "add", "Another widget17 note"])
    assert _search(capsys, db, "widget17").splitlines() == [
        "#20 Imported task number 17 about widget17",
        "#33 Another widget17 note",
    ]


# Brief: "the same holds for a second import into the same store"
def test_two_imports_in_a_row(tmp_path, capsys):
    db = tmp_path / "notes.json"
    first = _csv(tmp_path, ["1,Alpha plan,,,False", "2,Beta plan,,,False"], "a.csv")
    second = _csv(tmp_path, ["1,Gamma plan,,,False"], "b.csv")
    assert main(["--db", str(db), "import", str(first)]) == 0
    assert main(["--db", str(db), "import", str(second)]) == 0
    assert [(n.id, n.text) for n in Store(db).notes] == [
        (1, "Alpha plan"),
        (2, "Beta plan"),
        (3, "Gamma plan"),
    ]
    assert _search(capsys, db, "plan").splitlines() == [
        "#1 Alpha plan",
        "#2 Beta plan",
        "#3 Gamma plan",
    ]


# Brief: "If any row carries a due date that `notes add --due` would reject, the import must
# add nothing: print an error naming that CSV line as `line <n>` (the header is line 1), exit
# with status 1, and leave the store and its search index exactly as they were"
def test_invalid_due_imports_nothing(tmp_path, capsys):
    db = tmp_path / "notes.json"
    Store(db).add("Buy oat milk")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    path = _csv(
        tmp_path,
        [
            "1,First import row,,2024-03-01,False",
            "2,Second import row,,03/02/2024,False",
            "3,Third import row,,2024-02-30,False",
            "4,Fourth import row,,,False",
        ],
    )
    capsys.readouterr()
    assert main(["--db", str(db), "import", str(path)]) == 1
    captured = capsys.readouterr()
    assert "line 4" in captured.out + captured.err
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.name != "in.csv"}
    assert after == before
    assert _search(capsys, db, "import") == ""
