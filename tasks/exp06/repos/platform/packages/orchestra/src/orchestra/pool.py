"""Resource pools: named capacities that running jobs hold units of."""

from __future__ import annotations

from collections.abc import Mapping


class PoolError(ValueError):
    pass


class ResourcePool:
    def __init__(self, capacities: Mapping[str, int] | None = None) -> None:
        self.capacities = dict(capacities or {})
        for name, cap in self.capacities.items():
            if cap < 1:
                raise PoolError(f"capacity of {name!r} must be >= 1")
        self.in_use = {name: 0 for name in self.capacities}

    def check(self, job: str, request: Mapping[str, int]) -> None:
        """Raise if ``request`` could never be satisfied."""
        for name, amount in request.items():
            if name not in self.capacities:
                raise PoolError(f"{job!r} needs unknown resource {name!r}")
            if amount > self.capacities[name]:
                raise PoolError(
                    f"{job!r} needs {amount} {name!r} but capacity is {self.capacities[name]}"
                )

    def available(self, name: str) -> int:
        return self.capacities[name] - self.in_use[name]

    def can_acquire(self, request: Mapping[str, int]) -> bool:
        return all(self.available(n) >= a for n, a in request.items())

    def acquire(self, request: Mapping[str, int]) -> None:
        if not self.can_acquire(request):
            raise PoolError("insufficient capacity")
        for n, a in request.items():
            self.in_use[n] += a

    def release(self, request: Mapping[str, int]) -> None:
        for n, a in request.items():
            self.in_use[n] -= a
            if self.in_use[n] < 0:
                raise PoolError(f"released more {n!r} than was held")
