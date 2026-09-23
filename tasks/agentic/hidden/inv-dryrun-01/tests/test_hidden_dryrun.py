from invoicing.cli import main


def test_dry_run_create_does_not_write(tmp_path):
    db = tmp_path / "invoices.json"
    assert not db.exists()
    rc = main(["--db", str(db), "--dry-run", "create", "--customer", "Acme", "--amount", "10"])
    assert rc == 0
    assert not db.exists()
