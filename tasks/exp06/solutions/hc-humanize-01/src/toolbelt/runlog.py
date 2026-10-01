"""Runner log lines (format: ``docs/runner-logs.md``).

``humanize`` reproduces the legacy runner's durations: whole seconds, rounded
down; the largest non-zero unit of d/h/m/s plus the next smaller unit even
when it is zero (``1d 0h``, ``1m 0s``); under a minute just seconds; ``0s``.
"""

from __future__ import annotations

from datetime import UTC, datetime

_UNITS = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))


def humanize(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("duration must be non-negative")
    total = int(seconds)
    if total == 0:
        return "0s"
    parts = []
    rest = total
    for unit, size in _UNITS:
        parts.append((rest // size, unit))
        rest %= size
    first = next(i for i, (value, _) in enumerate(parts) if value)
    shown = parts[first : first + 2]
    return " ".join(f"{value}{unit}" for value, unit in shown)


def format_line(ts: datetime, job: str, attempt: int, status: str, seconds: float) -> str:
    stamp = ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{stamp} job={job} attempt={attempt} status={status} took={humanize(seconds)}"
