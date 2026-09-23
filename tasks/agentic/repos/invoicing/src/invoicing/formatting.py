"""Display formatting: money strings and (loosely) parsed dates.

``parse_invoice_date`` accepts either ISO (``2024-03-01``) or US
(``03/01/2024``) dates, because that is what customers paste into the
"issued on" field. ``invoicing.storage`` needs the same parsing for sorting
stored invoices and re-implements it separately - see the docstring there.
"""

from __future__ import annotations

from datetime import date


def format_money(amount: float) -> str:
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
