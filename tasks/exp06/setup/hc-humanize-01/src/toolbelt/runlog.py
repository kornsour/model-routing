"""Runner log lines (format: ``docs/runner-logs.md``)."""

from __future__ import annotations

from datetime import UTC, datetime


def format_line(ts: datetime, job: str, attempt: int, status: str, seconds: float) -> str:
    stamp = ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{stamp} job={job} attempt={attempt} status={status} took={seconds:.1f}s"
