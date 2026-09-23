from invoicing.models import Customer, Invoice
from invoicing.sync import send_all

CUSTOMER = Customer(id="c1", name="Acme")


def test_send_all_success():
    sent = []

    def sender(invoice):
        sent.append(invoice.id)

    invoices = [Invoice(id="i1", customer=CUSTOMER), Invoice(id="i2", customer=CUSTOMER)]
    result = send_all(invoices, sender)
    assert result == ["i1", "i2"]
    assert sent == ["i1", "i2"]
