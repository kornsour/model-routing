"""The ``errors`` report: the most frequent ERROR messages in a log."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from logproc.pipeline import read_entries
from logproc.redact import redact


def top_errors(log_path: str | Path, limit: int = 10) -> list[tuple[str, int]]:
    """Return ``(message, count)`` for the ``limit`` most frequent ERROR messages.

    Messages are masked first, so errors differing only in a secret count together.
    Most frequent first; ties keep the order in which the messages first appear.
    """
    counts = Counter(redact(e.message) for e in read_entries(log_path) if e.level == "ERROR")
    return counts.most_common(limit)


def format_errors(rows: list[tuple[str, int]]) -> str:
    return "\n".join(f"{count}  {message}" for message, count in rows)
