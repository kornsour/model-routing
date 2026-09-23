"""Time-window filtering of parsed entries for ``logproc report --since/--until``.

Boundaries and entry timestamps are parsed with
``logproc.timestamps.parse_timestamp`` so that every timestamp form the
README documents works on both sides of the comparison.
"""

from __future__ import annotations

from logproc.parser import LogEntry
from logproc.timestamps import parse_timestamp


def filter_window(
    entries: list[LogEntry], since: str | None = None, until: str | None = None
) -> list[LogEntry]:
    """Entries with ``since <= timestamp < until`` (each bound optional), in input order."""
    start = parse_timestamp(since) if since else None
    end = parse_timestamp(until) if until else None
    kept = []
    for entry in entries:
        instant = parse_timestamp(entry.timestamp)
        if start is not None and instant < start:
            continue
        if end is not None and instant >= end:
            continue
        kept.append(entry)
    return kept
