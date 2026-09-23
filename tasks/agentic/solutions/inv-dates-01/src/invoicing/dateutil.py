"""Shared date parsing: accepts ISO (``2024-03-01``) or US (``03/01/2024``)."""

from __future__ import annotations

from datetime import date


def parse_date(text: str) -> date:
    text = text.strip()
    if "-" in text:
        year, month, day = text.split("-")
    elif "/" in text:
        month, day, year = text.split("/")
    else:
        raise ValueError(f"unrecognized date: {text!r}")
    return date(int(year), int(month), int(day))
