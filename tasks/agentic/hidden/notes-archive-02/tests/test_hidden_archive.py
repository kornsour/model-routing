import pytest
from notes.archive import archive_done
from notes.cli import main
from notes.store import Store


def _store_with(tmp_path, texts, done_ids, name="notes.json"):
    store = Store(tmp_path / name)
    for text in texts:
        store.add(text)
    for note_id in done_ids:
        store.mark_done(note_id)
    return store


# Brief: "after `archive`, no completed note remains in the main store; every completed
# note is in the archive exactly once"
def test_consecutive_done_notes_are_all_moved(tmp_path):
    store = _store_with(tmp_path, ["a", "b", "c", "d", "e"], done_ids=[1, 2, 3, 5])
    archive_path = tmp_path / "archive.json"

    archive_done(store, archive_path)

    main_texts = [n.text for n in Store(store.path).notes]
    archived = sorted(n.text for n in Store(archive_path).notes)
    assert main_texts == ["d"]
    assert archived == ["a", "b", "c", "e"]


# Brief: "ids in the archive are unique like any store's ... must not depend on what ids
# the main store used"; "text, tags, due date and done flag intact"
def test_archive_ids_stay_unique_across_rounds(tmp_path):
    archive_path = tmp_path / "archive.json"
    old = Store(archive_path)
    old.add("already archived")
    old.mark_done(1)

    db = tmp_path / "notes.json"
    store = Store(db)
    store.add("keep")
    store.add("first done", tags=["home"], due="2024-03-01")
    store.mark_done(2)
    archive_done(store, archive_path)

    # A fresh note in the main store now gets id 2 again (max + 1), then gets archived too.
    store = Store(db)
    store.add("second done", tags=["work"])
    store.mark_done(store.notes[-1].id)
    archive_done(store, archive_path)

    archived = Store(archive_path).notes
    ids = [n.id for n in archived]
    assert len(ids) == len(set(ids)), f"duplicate archive ids: {ids}"
    assert sorted(n.text for n in archived) == ["already archived", "first done", "second done"]
    by_text = {n.text: n for n in archived}
    assert by_text["first done"].tags == ["home"]
    assert by_text["first done"].due == "2024-03-01"
    assert by_text["second done"].tags == ["work"]
    assert all(n.done for n in archived)
    assert [n.text for n in Store(db).notes] == ["keep"]


# Brief: "running `archive` again immediately is a no-op"
def test_second_run_is_a_noop(tmp_path):
    store = _store_with(tmp_path, ["a", "b"], done_ids=[1])
    archive_path = tmp_path / "archive.json"
    archive_done(store, archive_path)
    before = (store.path.read_text(), archive_path.read_text())

    assert archive_done(Store(store.path), archive_path) == []
    assert (store.path.read_text(), archive_path.read_text()) == before


# Brief: "losing a note is worse than duplicating one: if writing either file fails
# partway, every note is still in at least one of the two files"
def test_unwritable_archive_leaves_main_store_intact(tmp_path):
    store = _store_with(tmp_path, ["a", "b", "c"], done_ids=[1, 3])
    unwritable = tmp_path / "missing-dir" / "archive.json"

    with pytest.raises(OSError):
        archive_done(store, unwritable)

    assert [n.text for n in Store(store.path).notes] == ["a", "b", "c"]


# Brief: "`notes archive` ... via the CLI" - the command reflects the same guarantees
def test_cli_archive_moves_all_done_notes(tmp_path, capsys):
    db = tmp_path / "notes.json"
    _store_with(tmp_path, ["a", "b", "c"], done_ids=[2, 3])
    assert main(["--db", str(db), "archive"]) == 0
    assert "archived 2 notes" in capsys.readouterr().out
    assert [n.text for n in Store(db).notes] == ["a"]
    assert sorted(n.text for n in Store(f"{db}.archive.json").notes) == ["b", "c"]
