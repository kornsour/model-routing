from invoicing.cli import main
from invoicing.csvio import import_csv
from invoicing.customers import customer_totals
from invoicing.models import Customer, Invoice, LineItem
from invoicing.storage import Store


def _invoice(invoice_id, customer_id, name, price):
    return Invoice(
        id=invoice_id,
        customer=Customer(id=customer_id, name=name),
        items=[LineItem("Widget", 1, price)],
    )


# brief: "one row per customer; a customer is identified by name, compared case-insensitively
# and ignoring surrounding whitespace ... invoices created before this change (with random
# customer ids) must still group correctly"
def test_customer_totals_groups_legacy_ids_by_normalized_name():
    invoices = [
        _invoice("i1", "a1b2", "Acme", 10.0),
        _invoice("i2", "c3d4", "acme ", 5.0),
        _invoice("i3", "e5f6", " ACME", 2.5),
    ]
    rows = customer_totals(invoices)
    assert len(rows) == 1
    assert rows[0]["count"] == 3
    assert rows[0]["total"] == 17.5


# brief: "the display name is the name on the customer's first invoice in store order"
def test_customer_totals_display_name_is_first_seen():
    rows = customer_totals([_invoice("i1", "x", "Acme", 1.0), _invoice("i2", "y", "ACME", 1.0)])
    assert rows[0]["name"] == "Acme"


# brief: "genuinely different customers stay on separate rows"
def test_customer_totals_keeps_distinct_customers_apart():
    rows = customer_totals([_invoice("i1", "x", "Acme", 1.0), _invoice("i2", "y", "Acme Two", 1.0)])
    assert [row["name"] for row in rows] == ["Acme", "Acme Two"]
    assert [row["count"] for row in rows] == [1, 1]


# brief: "the same customer must get the same customer id whichever entry point created the
# invoice" - two creates
def test_cli_create_gives_same_customer_same_id(tmp_path):
    db = str(tmp_path / "invoices.json")
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "1"]) == 0
    assert main(["--db", db, "create", "--customer", "acme ", "--amount", "2"]) == 0
    ids = {inv.customer.id for inv in Store(db).all()}
    assert len(ids) == 1


# brief: "... whichever entry point (create, import-csv)" - create then import must agree
def test_import_csv_customer_id_matches_create(tmp_path):
    db = str(tmp_path / "invoices.json")
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "1"]) == 0
    csv_path = tmp_path / "in.csv"
    csv_path.write_text(
        "invoice_id,customer_name,description,quantity,unit_price\n"
        "x1,ACME,Widget,1,5.0\n"
        "x2, acme,Gadget,1,6.0\n"
    )
    imported = import_csv(csv_path)
    assert len({inv.customer.id for inv in imported}) == 1
    assert main(["--db", db, "import-csv", str(csv_path)]) == 0
    ids = {inv.customer.id for inv in Store(db).all()}
    assert len(ids) == 1


# brief: "different customers must not collide on id"
def test_distinct_customers_get_distinct_ids(tmp_path):
    db = str(tmp_path / "invoices.json")
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "1"]) == 0
    assert main(["--db", db, "create", "--customer", "Acme Two", "--amount", "1"]) == 0
    ids = {inv.customer.id for inv in Store(db).all()}
    assert len(ids) == 2


# brief: "report --by-customer shows Acme three times" is the symptom; one row is the fix
def test_cli_report_by_customer_one_row(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    for name, amount in (("Acme", "10"), ("ACME", "5"), ("acme ", "2.5")):
        assert main(["--db", db, "create", "--customer", name, "--amount", amount]) == 0
    capsys.readouterr()
    assert main(["--db", db, "report", "--by-customer"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == ["Acme\t3\t17.50"]
