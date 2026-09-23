"""Aggregation and pagination over parsed log entries."""

from __future__ import annotations

from collections import Counter

from logproc.parser import LogEntry


def count_by_level(entries: list[LogEntry]) -> dict[str, int]:
    return dict(Counter(e.level for e in entries))


def paginate(entries: list[LogEntry], page: int, page_size: int) -> list[LogEntry]:
    """Return the entries on ``page`` (1-indexed), ``page_size`` per page.

    Every entry must appear on exactly one page across ``page=1..N``.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    start = (page - 1) * page_size
    end = start + page_size
    return entries[start:end]
