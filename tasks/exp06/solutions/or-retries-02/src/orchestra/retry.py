"""Retry back-off."""

from __future__ import annotations

import hashlib

from orchestra.model import JobSpec


def jitter_fraction(name: str, attempt: int) -> float:
    """Deterministic value in [0, 1) for a job's failed attempt."""
    digest = hashlib.sha256(f"{name}:{attempt}".encode()).hexdigest()
    return int(digest[:8], 16) / 2**32


def backoff_delay(spec: JobSpec, failed_attempt: int) -> float:
    """Delay before the attempt after ``failed_attempt`` (1-based):
    ``backoff * 2 ** (failed_attempt - 1)``, capped at ``max_backoff``, then
    stretched by ``1 + jitter * jitter_fraction(name, failed_attempt)``."""
    base = min(spec.backoff * 2 ** (failed_attempt - 1), spec.max_backoff)
    return base * (1 + spec.jitter * jitter_fraction(spec.name, failed_attempt))


def should_retry(spec: JobSpec, failed_attempt: int, kind: str = "fail") -> bool:
    return kind in spec.retry_on and failed_attempt < spec.max_attempts
