"""Retry back-off."""

from __future__ import annotations

from orchestra.model import JobSpec


def backoff_delay(spec: JobSpec, failed_attempt: int) -> float:
    """Delay before the attempt after ``failed_attempt`` (1-based):
    ``backoff * 2 ** (failed_attempt - 1)``, capped at ``max_backoff``."""
    return min(spec.backoff * 2 ** (failed_attempt - 1), spec.max_backoff)


def should_retry(spec: JobSpec, failed_attempt: int) -> bool:
    return failed_attempt <= spec.max_attempts
