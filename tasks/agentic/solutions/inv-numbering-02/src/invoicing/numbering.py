"""Sequential invoice numbers (``INV-000001``).

Numbers are allocated from the store: the next one is one more than the
highest sequential number the store already holds, on disk or pending.
Legacy random ids are ignored, so a number is never reused and never
collides with an id that predates numbering.
"""

from __future__ import annotations

import re

from invoicing.storage import Store

PREFIX = "INV-"
_PATTERN = re.compile(r"^INV-(\d{6})$")


def format_number(n: int) -> str:
    return f"{PREFIX}{n:06d}"


def next_number(store: Store) -> str:
    """The next unused sequential number for ``store`` (disk plus pending)."""
    highest = 0
    for invoice in store.all():
        match = _PATTERN.match(invoice.id)
        if match:
            highest = max(highest, int(match.group(1)))
    return format_number(highest + 1)
