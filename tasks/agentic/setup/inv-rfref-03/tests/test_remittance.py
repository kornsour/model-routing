from invoicing.models import Customer, Invoice
from invoicing.reference import payment_reference
from invoicing.remittance import Payment, match_payments

CUSTOMER = Customer(id="c1", name="Acme")


def test_printed_reference_is_grouped_in_fours():
    ref = payment_reference("3fa85f64")
    assert ref.startswith("RF")
    assert all(len(group) == 4 for group in ref.split(" ")[:-1])


def test_unknown_reference_is_unmatched():
    invoices = [Invoice(id="3fa85f64", customer=CUSTOMER)]
    payment = Payment("2024-03-01", 5.0, "hello")
    assert match_payments(invoices, [payment]) == ([], [payment])
