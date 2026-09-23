"""Parses app log lines of the form ``TIMESTAMP LEVEL message``.

Example: ``2024-03-01T10:00:00 INFO server started``.
"""

from __future__ import annotations

from dataclasses import dataclass

LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


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
    if level not in LEVELS:
        return None
    return LogEntry(timestamp=timestamp, level=level, message=message)
