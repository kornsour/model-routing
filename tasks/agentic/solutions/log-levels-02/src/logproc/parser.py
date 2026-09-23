"""Parses app log lines of the form ``TIMESTAMP LEVEL message``.

Example: ``2024-03-01T10:00:00 INFO server started``.
"""

from __future__ import annotations

from dataclasses import dataclass

LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

LEVEL_ALIASES = {"WARN": "WARNING", "ERR": "ERROR", "FATAL": "CRITICAL", "SEVERE": "CRITICAL"}


def canonical_level(level: str) -> str | None:
    """The documented level for ``level`` (alias or canonical), or ``None`` if neither."""
    level = LEVEL_ALIASES.get(level, level)
    return level if level in LEVELS else None


@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str


def parse_line(line: str) -> LogEntry | None:
    """Parse one log line, or ``None`` if it isn't a recognized log line.

    Callers (see ``logproc.pipeline``) skip ``None`` results rather than
    failing the whole run on one malformed line.
    """
    line = line.rstrip("\n")
    if not line.strip():
        return None
    parts = line.split(" ", 2)
    if len(parts) < 3:
        return None
    timestamp, level, message = parts
    canonical = canonical_level(level)
    if canonical is None:
        return None
    return LogEntry(timestamp=timestamp, level=canonical, message=message)
