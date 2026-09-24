from invoicing.models import Customer, Invoice, LineItem
from invoicing.storage import Store
from invoicing.sync import sync_store

CUSTOMER = Customer(id="c1", name="Acme")


def test_sync_store_sends_new_invoices_once(tmp_path):
    store = Store(tmp_path / "invoices.json")
    store.add(Invoice(id="i1", customer=CUSTOMER, items=[LineItem("W", 1, 10.0)]))
    store.add(Invoice(id="i2", customer=CUSTOMER, items=[LineItem("G", 2, 5.0)]))
    store.flush()
    calls = []
    ledger = tmp_path / "ledger.json"

    assert sync_store(store, calls.append, ledger) == ["i1", "i2"]
    assert sync_store(store, calls.append, ledger) == []
    assert [inv.id for inv in calls] == ["i1", "i2"]
