from invoicing.calc import discount_amount, tax_amount, total
from invoicing.cli import main
from invoicing.models import Customer, Invoice, LineItem
from invoicing.statement import line_totals, statement_for

CUSTOMER = Customer(id="c1", name="Acme")


# brief: "a line of 1 x 1.005 must show 1.01"
def test_line_item_amount_rounds_half_up():
    assert LineItem("Widget", 1, 1.005).amount == 1.01
    assert LineItem("Widget", 7, 0.415).amount == 2.91


# brief: "every money figure - line amount, subtotal, ..."
def test_subtotal_rounds_half_up():
    invoice = Invoice(id="i1", customer=CUSTOMER, items=[LineItem("Widget", 1, 2.675)])
    assert invoice.subtotal == 2.68


# brief: "a 50% discount on 5.35 is 2.68"
def test_discount_rounds_half_up():
    assert discount_amount(5.35, 50) == 2.68


# brief: "25% tax on 10.70 is 2.68"
def test_tax_rounds_half_up():
    assert tax_amount(10.7, 0.25) == 2.68


# brief: "... total ..." end to end through calc.total
def test_total_rounds_half_up():
    invoice = Invoice(id="i1", customer=CUSTOMER, items=[LineItem("Widget", 7, 0.415)])
    assert total(invoice) == 2.91
    discounted = Invoice(
        id="i2", customer=CUSTOMER, items=[LineItem("Widget", 1, 5.35)], discount_pct=50
    )
    assert total(discounted) == 2.67  # 5.35 - 2.68


# brief: "the customer statement's lines and balance"
def test_statement_lines_and_balance_round_half_up():
    invoice = Invoice(id="i1", customer=CUSTOMER, items=[LineItem("Widget", 1, 1.005)])
    assert line_totals(invoice) == [("Widget", 1.01)]
    assert statement_for([invoice], "Acme")["balance"] == 1.01


# brief: "the statement command" is the user-facing surface for the same figures
def test_cli_statement_prints_half_up_figures(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    assert main(["--db", db, "create", "--customer", "Acme", "--amount", "2.675"]) == 0
    capsys.readouterr()
    assert main(["--db", db, "statement", "--customer", "Acme"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].endswith("\t2.68")
    assert lines[-1] == "balance 2.68"
