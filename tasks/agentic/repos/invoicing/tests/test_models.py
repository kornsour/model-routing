from invoicing.models import Customer, Invoice, LineItem


def test_line_item_amount():
    item = LineItem(description="Widget", quantity=3, unit_price=2.5)
    assert item.amount == 7.5


def test_invoice_subtotal():
    customer = Customer(id="c1", name="Acme")
    invoice = Invoice(
        id="i1",
        customer=customer,
        items=[
            LineItem("Widget", 2, 5.0),
            LineItem("Gadget", 1, 10.0),
        ],
    )
    assert invoice.subtotal == 20.0


def test_invoice_roundtrip_dict():
    customer = Customer(id="c1", name="Acme", email="ap@acme.test")
    invoice = Invoice(id="i1", customer=customer, items=[LineItem("Widget", 1, 5.0)])
    restored = Invoice.from_dict(invoice.to_dict())
    assert restored.id == invoice.id
    assert restored.customer.name == "Acme"
    assert restored.items[0].description == "Widget"
