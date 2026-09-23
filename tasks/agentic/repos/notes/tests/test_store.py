from notes.store import Store


def test_add_assigns_increasing_ids(tmp_path):
    store = Store(tmp_path / "notes.json")
    first = store.add("Buy milk")
    second = store.add("Walk the dog")
    assert first.id == 1
    assert second.id == 2


def test_mark_done(tmp_path):
    store = Store(tmp_path / "notes.json")
    note = store.add("Buy milk")
    assert store.mark_done(note.id) is True
    assert store.get(note.id).done is True
