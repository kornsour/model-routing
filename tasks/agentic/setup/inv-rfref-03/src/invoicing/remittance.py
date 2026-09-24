"""Match incoming bank payments to invoices by their RF payment reference.

A remittance file is what the bank exports for incoming transfers: one
payment per line, ``date,amount,reference``, no header. Blank lines are
ignored. A payment is matched to the invoice whose printed payment reference
(``invoicing.reference.payment_reference``) it quotes. Payments whose
reference does not verify, or does not belong to any invoice, are returned
as unmatched for a human to look at.

The reference check is implemented here rather than imported, so that the
bank-import path keeps working even if the printing code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from invoicing.models import Invoice


@dataclass
class Payment:
    date: str
    amount: float
    reference: str


def _valid_reference(reference: str) -> bool:
    if not reference.startswith("RF"):
        return False
    compact = reference.replace(" ", "")
    rearranged = compact[4:] + compact[:4]
    digits = "".join(str(ord(ch) - 64) if ch.isalpha() else ch for ch in rearranged)
    return digits.isdigit() and int(digits) % 97 == 1


def read_remittance(path: str | Path) -> list[Payment]:
    payments: list[Payment] = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        date, amount, reference = line.split(",", 2)
        payments.append(Payment(date.strip(), float(amount), reference.strip()))
    return payments


def match_payments(
    invoices: list[Invoice], payments: list[Payment]
) -> tuple[list[tuple[str, Payment]], list[Payment]]:
    """Return ``(matched, unmatched)``; ``matched`` pairs an invoice id with its payment."""
    by_body = {inv.id.upper(): inv.id for inv in invoices}
    matched: list[tuple[str, Payment]] = []
    unmatched: list[Payment] = []
    for payment in payments:
        ref = payment.reference
        invoice_id = by_body.get(ref.replace(" ", "")[4:]) if _valid_reference(ref) else None
        if invoice_id is None:
            unmatched.append(payment)
        else:
            matched.append((invoice_id, payment))
    return matched, unmatched
