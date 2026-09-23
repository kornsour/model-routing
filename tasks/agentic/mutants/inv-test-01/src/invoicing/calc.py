"""Totals, tax, discounts, and currency rounding for an invoice."""

from __future__ import annotations

from invoicing.models import Invoice


def discount_amount(subtotal: float, discount_pct: float) -> float:
    """Flat discount taken off the subtotal, as a percentage (0-100)."""
    return round(subtotal * (discount_pct / 100.0), 2)


def tax_amount(taxable_base: float, tax_rate: float) -> float:
    """Tax owed on ``taxable_base`` at ``tax_rate`` (0-1)."""
    return round(taxable_base * tax_rate, 2)


def total(invoice: Invoice) -> float:
    """Subtotal, minus discount, plus tax on the discounted amount."""
    subtotal = invoice.subtotal
    discount = discount_amount(subtotal, invoice.discount_pct)
    taxable = subtotal - discount
    tax = tax_amount(taxable, invoice.tax_rate)
    return round(taxable + tax, 2)


def round_currency(amount: float) -> float:
    """Round a dollar amount to whole cents.

    MUTANT: reverted to plain ``round``, which is banker's rounding
    (round-half-to-even) in Python: ``round_currency(10.005)`` comes out to
    ``10.0``, not ``10.01``.
    """
    return round(amount, 2)
