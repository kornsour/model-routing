"""Totals, tax, discounts, and currency rounding for an invoice."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

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
    """Round a dollar amount to whole cents, half-up.

    Plain ``round`` uses banker's rounding (round-half-to-even) in Python,
    which is not what a printed invoice should show a customer:
    ``round(0.005, 2)`` is ``0.0``, not ``0.01``. This rounds half-up instead,
    via ``Decimal`` to avoid float representation error at the boundary.
    """
    return float(Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
