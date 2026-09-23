from notes.cli import main


def test_dry_run_add_does_not_write(tmp_path):
    db = tmp_path / "notes.json"
    assert not db.exists()
    rc = main(["--db", str(db), "--dry-run", "add", "Buy milk"])
    assert rc == 0
    assert not db.exists()
