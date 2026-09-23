"""Display formatting: money strings and (loosely) parsed dates."""

from __future__ import annotations

from datetime import date

from invoicing.dateutil import parse_date


def format_money(amount: float) -> str:
    return f"${amount:,.2f}"


def parse_invoice_date(text: str) -> date:
    return parse_date(text)
