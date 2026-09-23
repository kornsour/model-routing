"""Due-date parsing for notes.

Accepts ISO (``2024-03-01``) or US (``03/01/2024``) dates, since that's what
people type on the command line. ``notes.cli`` needs the same parsing to
validate ``--due`` before saving and currently re-implements it - see the
docstring on the CLI's ``_parse_due`` helper.
"""

from __future__ import annotations

from datetime import date


def parse_due(text: str) -> date:
    text = text.strip()
    if "-" in text:
        year, month, day = text.split("-")
    elif "/" in text:
        month, day, year = text.split("/")
    else:
        raise ValueError(f"unrecognized date: {text!r}")
    return date(int(year), int(month), int(day))
