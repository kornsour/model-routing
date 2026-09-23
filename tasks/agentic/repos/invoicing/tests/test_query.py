from invoicing.models import Customer, Invoice
from invoicing.query import page_count, paginate

CUSTOMER = Customer(id="c1", name="Acme")


def _invoices(n):
    return [Invoice(id=f"i{i}", customer=CUSTOMER) for i in range(n)]


def test_paginate_single_page():
    invoices = _invoices(3)
    assert paginate(invoices, page=1, page_size=10) == invoices


def test_page_count():
    invoices = _invoices(25)
    assert page_count(invoices, page_size=10) == 3
