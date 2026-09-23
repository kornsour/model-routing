"""Payment references printed on invoices.

Every invoice carries an ISO 11649 structured creditor reference (an "RF
reference") derived from its id, so that a bank transfer quoting it can be
matched back to the invoice automatically (see ``invoicing.remittance``).

The reference body is the invoice id upper-cased with anything that is not
a letter or digit dropped. References are printed the way the standard
recommends for paper: "RF", the two check digits, then the body, split into
groups of four characters separated by single spaces. The electronic format
is the same string without the spaces.
"""

from __future__ import annotations


def reference_body(invoice_id: str) -> str:
    """The part of the reference after the check digits, for ``invoice_id``."""
    return "".join(ch for ch in invoice_id.upper() if ch.isalnum())


def _numeric(text: str) -> str:
    """Replace each letter with its number, as the check-digit algorithm needs."""
    return "".join(str(ord(ch) - ord("A") + 10) if ch.isalpha() else ch for ch in text)


def check_digits(body: str) -> str:
    """The two check digits for ``body``."""
    remainder = int(_numeric(body + "RF00")) % 97
    return f"{98 - remainder:02d}"


def payment_reference(invoice_id: str) -> str:
    """The printed RF reference for ``invoice_id``, e.g. ``"RF12 ABCD 1234"``."""
    body = reference_body(invoice_id)
    compact = "RF" + check_digits(body) + body
    return " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))
