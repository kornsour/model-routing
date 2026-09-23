from invoicing.cli import main
from invoicing.csvio import export_csv, import_csv
from invoicing.models import Customer, Invoice, LineItem
from invoicing.pipeline import generate_summary
from invoicing.storage import Store

CUSTOMER = Customer(id="c1", name="Acme")

LEGACY_RAW = {
    "id": "i1",
    "customer": {"id": "c1", "name": "Acme", "email": ""},
    "items": [{"description": "Widget", "quantity": 1, "unit_price": 10.0}],
    "tax_rate": 0.0,
    "discount_pct": 0.0,
    "status": "draft",
}

LEGACY_CSV = "invoice_id,customer_name,description,quantity,unit_price\ni1,Acme,Widget,2,5.0\n"


# brief: "store files written before this change carry no currency and must load as USD"
def test_legacy_json_record_loads_as_usd():
    invoice = Invoice.from_dict(dict(LEGACY_RAW))
    assert invoice.currency == "USD"


# brief: "the JSON store must round-trip the currency"
def test_json_roundtrip_keeps_currency():
    invoice = Invoice(id="i1", customer=CUSTOMER, items=[LineItem("W", 1, 5.0)], currency="EUR")
    assert Invoice.from_dict(invoice.to_dict()).currency == "EUR"


# brief: "a store file written before this change ... loads as USD" - through the Store, not
# just from_dict, so the on-disk path is exercised
def test_legacy_store_file_loads_as_usd(tmp_path):
    path = tmp_path / "invoices.json"
    path.write_text(
        '[{"id": "i1", "customer": {"id": "c1", "name": "Acme", "email": ""}, '
        '"items": [], "tax_rate": 0.0, "discount_pct": 0.0, "status": "draft"}]'
    )
    assert [inv.currency for inv in Store(path).all()] == ["USD"]


# brief: "import-csv must accept files exported before this change (no currency column,
# treated as USD)"
def test_legacy_csv_without_currency_column_imports_as_usd(tmp_path):
    path = tmp_path / "legacy.csv"
    path.write_text(LEGACY_CSV)
    imported = import_csv(path)
    assert len(imported) == 1
    assert imported[0].currency == "USD"
    assert imported[0].items[0].quantity == 2


# brief: "CSV export adds a trailing currency column ... round-trips"
def test_csv_export_has_trailing_currency_column_and_roundtrips(tmp_path):
    invoice = Invoice(id="i1", customer=CUSTOMER, items=[LineItem("W", 1, 5.0)], currency="EUR")
    path = tmp_path / "out.csv"
    export_csv([invoice], path)
    header = path.read_text().splitlines()[0]
    assert header == "invoice_id,customer_name,description,quantity,unit_price,currency"
    assert import_csv(path)[0].currency == "EUR"


# brief: "generate_summary keeps count and total and adds by_currency mapping each code to
# {count, total}"
def test_summary_by_currency(tmp_path):
    store = Store(tmp_path / "invoices.json")
    store.add(Invoice(id="a", customer=CUSTOMER, items=[LineItem("W", 1, 10.0)]))
    store.add(Invoice(id="b", customer=CUSTOMER, items=[LineItem("W", 1, 5.0)], currency="EUR"))
    store.add(Invoice(id="c", customer=CUSTOMER, items=[LineItem("W", 1, 7.0)], currency="EUR"))
    store.flush()
    summary = generate_summary(store)
    assert summary["count"] == 3
    assert summary["total"] == 22.0
    assert summary["by_currency"] == {
        "EUR": {"count": 2, "total": 12.0},
        "USD": {"count": 1, "total": 10.0},
    }


# brief: "create --currency eur stores the code upper-cased" and "report prints its existing
# line followed by one line per currency"
def test_cli_create_with_currency_and_report(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    assert (
        main(["--db", db, "create", "--customer", "Acme", "--amount", "10", "--currency", "eur"])
        == 0
    )
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "4"]) == 0
    assert [inv.currency for inv in Store(db).all()] == ["EUR", "USD"]
    capsys.readouterr()
    assert main(["--db", db, "report"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "2 invoices, total 14.00"
    assert any(line.strip() == "EUR: 1 invoices, total 10.00" for line in out[1:])
    assert any(line.strip() == "USD: 1 invoices, total 4.00" for line in out[1:])


# brief: "create without --currency keeps producing USD invoices"
def test_cli_create_default_currency_is_usd(tmp_path):
    db = str(tmp_path / "invoices.json")
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "1"]) == 0
    assert Store(db).all()[0].currency == "USD"
