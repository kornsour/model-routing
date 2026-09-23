"""Timestamp parsing for log entries.

Accepts ISO-8601 (``2024-03-01T10:00:00``) or space-separated
(``2024-03-01 10:00:00``) timestamps, since both show up depending on which
service emitted the line. ``logproc.pipeline`` needs the same parsing to sort
a report's entries and currently re-implements it - see the docstring on the
pipeline's ``_parse_timestamp`` helper.
"""

from __future__ import annotations

from datetime import datetime


def parse_timestamp(text: str) -> datetime:
    text = text.strip()
    normalized = text.replace("T", " ", 1) if "T" in text else text
    return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
