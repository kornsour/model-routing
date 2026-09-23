"""Structured fields carried inside log messages. See the README's "Latency" section."""

from __future__ import annotations

import re

_UNITS_MS = {"us": 0.001, "ms": 1.0, "s": 1000.0}
_DURATION = re.compile(r"(\d+)(us|ms|s)")
_TOOK = re.compile(r"\btook=(\S+)")


def parse_duration(text: str) -> float:
    """Parse a duration such as ``12ms`` and return it in milliseconds.

    Raises ``ValueError`` for anything that is not a documented duration.
    """
    match = _DURATION.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"not a duration: {text!r}")
    return int(match.group(1)) * _UNITS_MS[match.group(2)]


def extract_duration(message: str) -> float | None:
    """Return the ``took=`` duration in ``message`` in milliseconds, or ``None``."""
    match = _TOOK.search(message)
    if match is None:
        return None
    try:
        return parse_duration(match.group(1))
    except ValueError:
        return None
