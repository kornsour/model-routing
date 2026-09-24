import json

from invoicing.cli import main
from invoicing.models import Customer, Invoice, LineItem
from invoicing.storage import Store

CUSTOMER = Customer(id="c1", name="Acme")
HEADER = "invoice_id,customer_name,description,quantity,unit_price"


def _seed(path, *ids):
    store = Store(path)
    for invoice_id in ids:
        store.add(Invoice(id=invoice_id, customer=CUSTOMER, items=[LineItem("W", 1, 1.0)]))
    store.flush()


# brief: "create assigns INV-000001, INV-000002, ... (zero-padded to six digits)"
def test_create_assigns_sequential_numbers(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "1"]) == 0
    assert "INV-000001" in capsys.readouterr().out
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "1"]) == 0
    assert [inv.id for inv in Store(db).all()] == ["INV-000001", "INV-000002"]


# brief: "the next number is one more than the highest sequential number already in the store,
# ignoring legacy random ids" (so neither a count nor the last record decides it)
def test_next_number_ignores_legacy_ids_and_gaps(tmp_path):
    db = tmp_path / "invoices.json"
    _seed(db, "a1b2c3d4", "INV-000005", "9f8e7d6c", "INV-000002")
    assert main(["--db", str(db), "create", "--customer", "Acme", "--amount", "1"]) == 0
    assert Store(db).all()[-1].id == "INV-000006"


# brief: "import-csv rows with a blank invoice_id each become their own single-item invoice and
# get distinct numbers in one run, above anything on disk or already pending"
def test_import_blank_ids_get_distinct_numbers_in_one_run(tmp_path):
    db = tmp_path / "invoices.json"
    _seed(db, "INV-000002", "legacy01")
    csv_path = tmp_path / "in.csv"
    csv_path.write_text(
        f"{HEADER}\n,Acme,Widget,1,5.0\n,Acme,Gadget,2,6.0\nkeep-me,Acme,Gizmo,1,7.0\n"
    )
    assert main(["--db", str(db), "import-csv", str(csv_path)]) == 0
    invoices = Store(db).all()
    ids = [inv.id for inv in invoices]
    assert len(ids) == len(set(ids)) == 5
    assert "keep-me" in ids
    new = sorted(i for i in ids if i.startswith("INV-") and i != "INV-000002")
    assert new == ["INV-000003", "INV-000004"]
    by_id = {inv.id: inv for inv in invoices}
    assert [item.description for item in by_id["INV-000003"].items] == ["Widget"]
    assert [item.description for item in by_id["INV-000004"].items] == ["Gadget"]


# brief: "rows with a non-blank id keep it ... legacy ids must keep loading, listing and
# exporting as before, so re-importing an export round-trips"
def test_export_import_roundtrip_keeps_legacy_ids(tmp_path):
    db = tmp_path / "invoices.json"
    _seed(db, "a1b2c3d4", "INV-000001")
    out = tmp_path / "out.csv"
    assert main(["--db", str(db), "export-csv", str(out)]) == 0
    db2 = tmp_path / "second.json"
    assert main(["--db", str(db2), "import-csv", str(out)]) == 0
    assert sorted(inv.id for inv in Store(db2).all()) == ["INV-000001", "a1b2c3d4"]


# brief: "numbers are never reused" - the number after an import continues from the imported ones
def test_create_after_import_continues_sequence(tmp_path):
    db = tmp_path / "invoices.json"
    csv_path = tmp_path / "in.csv"
    csv_path.write_text(f"{HEADER}\n,Acme,Widget,1,5.0\n,Acme,Gadget,1,6.0\n")
    assert main(["--db", str(db), "import-csv", str(csv_path)]) == 0
    assert main(["--db", str(db), "create", "--customer", "Acme", "--amount", "1"]) == 0
    records = json.loads(db.read_text())
    assert [rec["id"] for rec in records] == ["INV-000001", "INV-000002", "INV-000003"]
