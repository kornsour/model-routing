from invoicing.calc import discount_amount, tax_amount, total
from invoicing.models import Customer, Invoice, LineItem


def test_tax_amount():
    assert tax_amount(100.0, 0.08) == 8.0


def test_discount_amount():
    assert discount_amount(100.0, 10) == 10.0


def test_total_with_tax_and_discount():
    customer = Customer(id="c1", name="Acme")
    invoice = Invoice(
        id="i1",
        customer=customer,
        items=[LineItem("Widget", 1, 100.0)],
        tax_rate=0.08,
        discount_pct=10,
    )
    # subtotal 100, discount 10 -> taxable 90, tax 7.2 -> total 97.2
    assert total(invoice) == 97.2
