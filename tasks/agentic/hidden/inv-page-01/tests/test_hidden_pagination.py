from invoicing.models import Customer, Invoice
from invoicing.query import paginate

CUSTOMER = Customer(id="c1", name="Acme")


def test_paginate_exact_multiple_covers_every_invoice():
    invoices = [Invoice(id=f"i{i}", customer=CUSTOMER) for i in range(6)]
    page_size = 3
    seen = []
    for page in (1, 2):
        seen.extend(paginate(invoices, page=page, page_size=page_size))
    assert seen == invoices
