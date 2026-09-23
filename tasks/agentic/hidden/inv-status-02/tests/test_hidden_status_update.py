import json

from invoicing.cli import main
from invoicing.models import Customer, Invoice, LineItem
from invoicing.storage import Store

CUSTOMER = Customer(id="c1", name="Acme")


def _seeded_store(path):
    store = Store(path)
    store.add(Invoice(id="i1", customer=CUSTOMER, items=[LineItem("W", 1, 10.0)]))
    store.flush()
    return store


# brief: "re-adding an invoice whose id the store already holds must replace the earlier
# version ... in what the store reports before flushing"
def test_readded_invoice_replaces_earlier_version_before_flush(tmp_path):
    store = _seeded_store(tmp_path / "invoices.json")
    invoice = store.all()[0]
    invoice.status = "paid"
    store.add(invoice)
    reported = store.all()
    assert [inv.id for inv in reported] == ["i1"]
    assert reported[0].status == "paid"


# brief: "... and in the file after flushing"
def test_readded_invoice_replaces_earlier_version_on_disk(tmp_path):
    path = tmp_path / "invoices.json"
    store = _seeded_store(path)
    invoice = store.all()[0]
    invoice.status = "paid"
    store.add(invoice)
    store.flush()
    on_disk = json.loads(path.read_text())
    assert [rec["id"] for rec in on_disk] == ["i1"]
    assert on_disk[0]["status"] == "paid"
    assert [inv.status for inv in Store(path).all()] == ["paid"]


# brief: "the store must never report the same id twice" - even when the same invoice is
# buffered twice before a flush
def test_same_invoice_added_twice_is_reported_once(tmp_path):
    store = Store(tmp_path / "invoices.json")
    invoice = Invoice(id="i1", customer=CUSTOMER)
    store.add(invoice)
    store.add(invoice)
    assert [inv.id for inv in store.all()] == ["i1"]
    store.flush()
    assert [inv.id for inv in Store(store.path).all()] == ["i1"]


# brief: "adding invoices with new ids must keep working" (and the earlier ones keep their place)
def test_new_ids_still_append_in_order(tmp_path):
    store = _seeded_store(tmp_path / "invoices.json")
    store.add(Invoice(id="i2", customer=CUSTOMER))
    store.add(Invoice(id="i3", customer=CUSTOMER))
    assert [inv.id for inv in store.all()] == ["i1", "i2", "i3"]
    store.flush()
    assert [inv.id for inv in Store(store.path).all()] == ["i1", "i2", "i3"]


# brief: "mark-paid reports success but the invoice still shows draft in list afterwards"
def test_cli_mark_paid_is_visible_in_list(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "10"]) == 0
    invoice_id = capsys.readouterr().out.split()[2]
    assert main(["--db", db, "mark-paid", invoice_id]) == 0
    capsys.readouterr()
    assert main(["--db", db, "list"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].split("\t")[2] == "paid"


# brief: "report must not count an updated invoice twice"
def test_cli_report_count_unchanged_after_mark_sent(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "10"]) == 0
    invoice_id = capsys.readouterr().out.split()[2]
    assert main(["--db", db, "mark-sent", invoice_id]) == 0
    capsys.readouterr()
    assert main(["--db", db, "report"]) == 0
    assert capsys.readouterr().out.strip() == "1 invoices, total 10.00"
