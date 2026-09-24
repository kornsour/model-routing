"""Latency percentiles and the slow-request filter. See the README's "Latency" section."""

from __future__ import annotations

import math

from logproc.fields import extract_duration
from logproc.parser import LogEntry

PERCENTILES = (50, 90, 99)


def percentile(values: list[float], p: int) -> float:
    """The ``p``-th percentile of ``values`` (nearest-rank method)."""
    ordered = sorted(values)
    index = max(math.ceil(p * len(ordered) / 100) - 1, 0)
    return ordered[index]


def summarize(entries: list[LogEntry]) -> dict:
    durations = [d for d in (extract_duration(e.message) for e in entries) if d is not None]
    if not durations:
        return {"count": 0}
    summary: dict = {"count": len(durations)}
    for p in PERCENTILES:
        summary[f"p{p}"] = percentile(durations, p)
    summary["max"] = max(durations)
    return summary


def format_summary(summary: dict) -> str:
    parts = [f"count={summary['count']}"]
    for key in ("p50", "p90", "p99", "max"):
        if key in summary:
            parts.append(f"{key}={format(summary[key], 'g')}")
    return " ".join(parts)


def slow_entries(entries: list[LogEntry], threshold_ms: float) -> list[LogEntry]:
    """Entries that took longer than ``threshold_ms``, in log order."""
    slow = []
    for entry in entries:
        took = extract_duration(entry.message)
        if took is not None and took > threshold_ms:
            slow.append(entry)
    return slow
