"""Retry decisions. Backoff delays moved to ``toolbelt.backoff``."""

from __future__ import annotations

import warnings

from toolbelt.backoff import Backoff

from orchestra.model import JobSpec


def job_backoff(spec: JobSpec) -> Backoff:
    """The job's backoff policy (never jittered: simulation is deterministic)."""
    return Backoff(spec.backoff, spec.backoff_factor, spec.max_backoff)


def backoff_delay(spec: JobSpec, failed_attempt: int) -> float:
    """Deprecated: use ``toolbelt.backoff.Backoff`` (or ``job_backoff``)."""
    warnings.warn(
        "orchestra.retry.backoff_delay is deprecated; use toolbelt.backoff.Backoff",
        DeprecationWarning,
        stacklevel=2,
    )
    return job_backoff(spec).delay(failed_attempt)


def should_retry(spec: JobSpec, failed_attempt: int) -> bool:
    return failed_attempt < spec.max_attempts
