from notes.cli import main
from notes.store import Store


def test_import_into_nonempty_store_has_no_id_collisions(tmp_path):
    db = tmp_path / "notes.json"
    store = Store(db)
    store.add("Existing one")
    store.add("Existing two")

    csv_path = tmp_path / "import.csv"
    csv_path.write_text("id,text,tags,due,done\n1,Imported one,,,False\n2,Imported two,,,False\n")

    rc = main(["--db", str(db), "import", str(csv_path)])
    assert rc == 0

    final = Store(db)
    ids = [n.id for n in final.notes]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"
    assert len(final.notes) == 4
