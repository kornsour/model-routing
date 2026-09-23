"""Display formatting: money strings and (loosely) parsed dates.

``parse_invoice_date`` accepts an RFC 3339 timestamp (``2024-03-01T10:00:00Z``,
``2024-03-01T23:30:00-05:00``, fractional seconds), ISO (``2024-03-01``) or US
(``03/01/2024``) dates, because that is what customers paste into the
"issued on" field, and returns the UTC calendar day. ``invoicing.storage``
needs the same parsing for sorting stored invoices and re-implements it
separately - see the docstring there.
"""

from __future__ import annotations

from datetime import UTC, date, datetime


def format_money(amount: float) -> str:
    return f"${amount:,.2f}"


def parse_invoice_instant(text: str) -> datetime:
    """Parse ``text`` to a timezone-aware UTC datetime.

    RFC 3339 timestamps keep their offset and are converted to UTC; a plain
    ISO or US date means midnight UTC on that day.
    """
    text = text.strip()
    if "T" in text or "t" in text:
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"unrecognized date: {text!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    if "/" in text:
        month, day, year = text.split("/")
    elif "-" in text:
        year, month, day = text.split("-")
    else:
        raise ValueError(f"unrecognized date: {text!r}")
    return datetime(int(year), int(month), int(day), tzinfo=UTC)


def parse_invoice_date(text: str) -> date:
    return parse_invoice_instant(text).date()
