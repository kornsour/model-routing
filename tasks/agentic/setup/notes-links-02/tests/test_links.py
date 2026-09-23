from notes.cli import main
from notes.links import expand_links, linked_ids, linked_notes
from notes.store import Store


def test_linked_ids_in_order_without_repeats():
    assert linked_ids("see #3 then #1 and #3 again") == [3, 1]


def test_expand_links_and_linked_notes(tmp_path):
    store = Store(tmp_path / "notes.json")
    store.add("Buy milk")
    hub = store.add("After #1 do #9")
    assert expand_links(store, hub.text) == "After [#1 Buy milk] do [#9 ?]"
    assert [n.id for n in linked_notes(store, hub)] == [1]


def test_show_command(tmp_path, capsys):
    db = tmp_path / "notes.json"
    store = Store(db)
    store.add("Buy milk")
    store.add("Then #1")
    assert main(["--db", str(db), "show", "2"]) == 0
    out = capsys.readouterr().out
    assert "[ ] #2 Then [#1 Buy milk]" in out
    assert "  -> #1 Buy milk" in out
