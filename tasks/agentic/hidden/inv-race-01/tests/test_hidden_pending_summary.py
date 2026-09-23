from invoicing.models import Customer, Invoice, LineItem
from invoicing.pipeline import generate_summary
from invoicing.storage import Store


def test_summary_reflects_unflushed_invoice(tmp_path):
    store = Store(tmp_path / "invoices.json")
    customer = Customer(id="c1", name="Acme")
    store.add(Invoice(id="i1", customer=customer, items=[LineItem("Widget", 1, 10.0)]))
    # Deliberately not flushed.
    summary = generate_summary(store)
    assert summary["count"] == 1
    assert summary["total"] == 10.0
