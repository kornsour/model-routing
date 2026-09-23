import builtins
import io

from notes.cli import main
from notes.store import Store


def _count_reads(monkeypatch, path):
    """Count every open of ``path`` for reading, whichever API does it."""
    counter = {"n": 0}
    real_open = io.open

    def counting_open(file, mode="r", *args, **kwargs):
        if str(file) == str(path) and "r" in mode and "+" not in mode:
            counter["n"] += 1
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(io, "open", counting_open)
    monkeypatch.setattr(builtins, "open", counting_open)
    return counter


# Brief: "`show` must read the notes file at most once per invocation, however many
# references the note contains"
def test_show_reads_store_at_most_once(tmp_path, monkeypatch, capsys):
    db = tmp_path / "notes.json"
    store = Store(db)
    for i in range(40):
        store.add(f"task {i}")
    refs = " ".join(f"#{i}" for i in range(1, 41))
    hub = store.add(f"depends on {refs}")

    counter = _count_reads(monkeypatch, db)
    assert main(["--db", str(db), "show", str(hub.id)]) == 0
    out = capsys.readouterr().out
    assert "[#1 task 0]" in out
    assert "[#40 task 39]" in out
    assert out.count("  -> #") == 40
    assert counter["n"] <= 1, f"store file was read {counter['n']} times"


# Brief: "a `Store` that is already open must still return a note another `Store` instance
# has since saved to the same file"
def test_open_store_sees_other_process_saves(tmp_path):
    db = tmp_path / "notes.json"
    Store(db).add("first")

    watcher = Store(db)
    assert watcher.get(2) is None

    other = Store(db)
    new = other.add("second")
    found = watcher.get(new.id)
    assert found is not None
    assert found.text == "second"

    other.mark_done(1)
    first = watcher.get(1)
    assert first is not None
    assert first.done is True
