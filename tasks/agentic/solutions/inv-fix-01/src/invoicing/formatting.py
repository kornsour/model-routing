"""Display formatting: money strings and (loosely) parsed dates."""

from __future__ import annotations

from datetime import date


def format_money(amount: float) -> str:
    if amount < 0:
        return f"-${-amount:,.2f}"
    return f"${amount:,.2f}"


def parse_invoice_date(text: str) -> date:
    text = text.strip()
    if "-" in text:
        year, month, day = text.split("-")
    elif "/" in text:
        month, day, year = text.split("/")
    else:
        raise ValueError(f"unrecognized date: {text!r}")
    return date(int(year), int(month), int(day))
