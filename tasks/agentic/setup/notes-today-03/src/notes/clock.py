"""The notes tool's notion of "today".

Every date-relative feature - ``list --overdue``, ``agenda`` and ``remind`` -
takes today's date from :func:`today`. The global ``--today YYYY-MM-DD``
option sets it for one invocation, so anyone can reproduce exactly what a
teammate saw on a given day; without the option, today is the local calendar
date.
"""

from __future__ import annotations

from datetime import date

_override: date | None = None


def set_today(value: date | None) -> None:
    """Pin today to ``value`` (``None`` goes back to the real local date)."""
    global _override
    _override = value


def today() -> date:
    return _override if _override is not None else date.today()
