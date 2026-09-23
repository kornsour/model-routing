from invoicing.calc import total
from invoicing.cli import main
from invoicing.models import Customer, Invoice, LineItem
from invoicing.storage import Store

CUSTOMER = Customer(id="c1", name="Acme")


def _invoice() -> Invoice:
    return Invoice(
        id="i1",
        customer=CUSTOMER,
        items=[LineItem("Widget", 2, 100.0)],
        tax_rate=0.08,
        discount_pct=10,
    )


# brief: "an invoice with subtotal 200, a 10% discount and 8% tax is worth 194.40: the discount
# comes off the subtotal, then tax applies to the discounted amount"
def test_total_applies_tax_to_discounted_amount():
    assert total(_invoice()) == 194.4


# brief: "the figure must survive the store" - a later invocation reading the same file must
# see the same discount
def test_discount_survives_store_roundtrip(tmp_path):
    path = tmp_path / "invoices.json"
    store = Store(path)
    store.add(_invoice())
    store.flush()
    reloaded = Store(path).all()
    assert reloaded[0].discount_pct == 10
    assert total(reloaded[0]) == 194.4


# brief: "report must show the same total the create command printed, in a later invocation
# reading the same store file"
def test_cli_create_then_report_agree_with_discount(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    argv = ["--db", db, "create", "--customer", "Acme", "--quantity", "2", "--amount", "100"]
    assert main([*argv, "--tax-rate", "0.08", "--discount-pct", "10"]) == 0
    created = capsys.readouterr().out.strip()
    assert created.endswith("for 194.40")
    assert main(["--db", db, "report"]) == 0
    assert capsys.readouterr().out.strip() == "1 invoices, total 194.40"


# brief: "invoices without a discount are unaffected"
def test_no_discount_unchanged(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    assert (
        main(["--db", db, "create", "--customer", "Acme", "--amount", "100", "--tax-rate", "0.08"])
        == 0
    )
    capsys.readouterr()
    assert main(["--db", db, "report"]) == 0
    assert capsys.readouterr().out.strip() == "1 invoices, total 108.00"
