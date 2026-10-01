"""Retry backoff, shared by the scheduler, the runner's HTTP client and ledger.

``Backoff(base, factor=2.0, cap=inf, jitter="none", seed=None)``: the delay
after failed attempt ``n`` (1-based) is ``d = min(base * factor ** (n - 1),
cap)``. ``"full"`` jitter draws uniformly from ``[0, d]``; ``"equal"`` jitter
is ``d / 2`` plus a uniform draw from ``[0, d / 2]``. Draws come from
``random.Random(f"{seed}:{n}")``, so a seed and attempt always give the same
delay whatever order delays are asked for; jitter therefore needs a seed. The
simulator never uses jitter: its runs must be pure functions of their input.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

JITTER = ("none", "full", "equal")


@dataclass(frozen=True)
class Backoff:
    base: float
    factor: float = 2.0
    cap: float = math.inf
    jitter: str = "none"
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.base < 0:
            raise ValueError("base must be >= 0")
        if self.factor < 1:
            raise ValueError("factor must be >= 1")
        if self.cap < 0:
            raise ValueError("cap must be >= 0")
        if self.jitter not in JITTER:
            raise ValueError(f"jitter must be one of {JITTER}")
        if self.jitter != "none" and not isinstance(self.seed, int):
            raise ValueError("jitter needs an int seed")

    def delay(self, failed_attempt: int) -> float:
        if isinstance(failed_attempt, bool) or not isinstance(failed_attempt, int):
            raise TypeError("failed_attempt must be an int")
        if failed_attempt < 1:
            raise ValueError("failed_attempt is 1-based")
        d = min(self.base * self.factor ** (failed_attempt - 1), self.cap)
        if self.jitter == "none":
            return d
        rng = random.Random(f"{self.seed}:{failed_attempt}")
        if self.jitter == "full":
            return rng.uniform(0, d)
        return d / 2 + rng.uniform(0, d / 2)

    def schedule(self, n: int) -> list[float]:
        return [self.delay(k) for k in range(1, n + 1)]

    def total(self, n: int) -> float:
        return sum(self.schedule(n))
