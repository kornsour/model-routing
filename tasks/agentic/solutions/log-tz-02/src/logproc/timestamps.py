"""Timestamp parsing for log entries.

Accepts every form the README documents: ISO-8601 (``2024-03-01T10:00:00``)
or space-separated (``2024-03-01 10:00:00``), with optional fractional
seconds, an optional ``Z`` or ``+HH:MM`` offset. A timestamp without an
offset is UTC, so every result is offset-aware and comparable with every
other. ``logproc.pipeline`` needs the same parsing to sort a report's entries
and delegates here.
"""

from __future__ import annotations

from datetime import UTC, datetime


def parse_timestamp(text: str) -> datetime:
    text = text.strip()
    if not text or text[0] not in "0123456789" or len(text) < len("2024-03-01 10:00:00"):
        raise ValueError(f"unrecognized timestamp: {text!r}")
    normalized = text.replace(" ", "T", 1)
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
