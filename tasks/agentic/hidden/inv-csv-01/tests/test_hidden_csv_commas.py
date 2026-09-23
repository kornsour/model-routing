from invoicing.csvio import export_csv, import_csv
from invoicing.models import Customer, Invoice, LineItem


def test_export_import_roundtrip_with_embedded_comma(tmp_path):
    customer = Customer(id="c1", name="Acme, Inc.")
    invoice = Invoice(
        id="i1",
        customer=customer,
        items=[LineItem("Widgets, assorted", 2, 5.0)],
    )
    path = tmp_path / "invoices.csv"
    export_csv([invoice], path)

    imported = import_csv(path)
    assert len(imported) == 1
    assert imported[0].customer.name == "Acme, Inc."
    assert imported[0].items[0].description == "Widgets, assorted"
