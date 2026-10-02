"""Expected cost and wall time of a job under a retry policy.

Each attempt fails independently with probability ``p_fail``; attempt ``k``
(1-based) happens with probability ``p_fail ** (k - 1)``, up to
``max_attempts``. The backoff wait after failed attempt ``k`` only happens if
attempt ``k + 1`` does, so it is weighted by ``p_fail ** k``::

    cost    = sum_k P(k) * duration * rate_per_second
    seconds = sum_k P(k) * duration + sum_{k < max} P(k + 1) * delay(k)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from orchestra.model import JobSpec
from orchestra.retry import job_backoff

from ledger.rates import rate_for


@dataclass(frozen=True)
class Estimate:
    cost: float
    seconds: float


def estimate(spec: JobSpec, rates: Mapping[str, float], p_fail: float) -> Estimate:
    if not 0 <= p_fail <= 1:
        raise ValueError("p_fail must be between 0 and 1")
    per_second = sum(units * float(rate_for(rates, pool)) for pool, units in spec.resources.items())
    backoff = job_backoff(spec)
    probs = [p_fail ** (k - 1) for k in range(1, spec.max_attempts + 1)]
    run_seconds = sum(p * spec.duration for p in probs)
    waits = sum(probs[k] * backoff.delay(k) for k in range(1, spec.max_attempts))
    return Estimate(cost=run_seconds * per_second, seconds=run_seconds + waits)
