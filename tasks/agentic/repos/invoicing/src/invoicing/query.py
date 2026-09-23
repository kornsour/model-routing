"""Listing and pagination over a sequence of invoices."""

from __future__ import annotations

from invoicing.models import Invoice


def paginate(invoices: list[Invoice], page: int, page_size: int) -> list[Invoice]:
    """Return the invoices on ``page`` (1-indexed), ``page_size`` per page.

    ``page=1`` is the first page. Callers rely on every invoice appearing on
    exactly one page across ``page=1..N`` with no gaps or repeats.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    start = (page - 1) * page_size
    end = start + page_size - 1
    return invoices[start:end]


def page_count(invoices: list[Invoice], page_size: int) -> int:
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    n = len(invoices)
    return (n + page_size - 1) // page_size if n else 0
