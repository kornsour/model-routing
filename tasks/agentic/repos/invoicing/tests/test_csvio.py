from invoicing.csvio import export_csv, import_csv
from invoicing.models import Customer, Invoice, LineItem


def test_export_then_import_roundtrip(tmp_path):
    customer = Customer(id="c1", name="Acme")
    invoice = Invoice(
        id="i1",
        customer=customer,
        items=[LineItem("Widget", 2, 5.0), LineItem("Gadget", 1, 10.0)],
    )
    path = tmp_path / "invoices.csv"
    export_csv([invoice], path)

    imported = import_csv(path)
    assert len(imported) == 1
    assert imported[0].id == "i1"
    assert len(imported[0].items) == 2
    assert imported[0].items[0].description == "Widget"
