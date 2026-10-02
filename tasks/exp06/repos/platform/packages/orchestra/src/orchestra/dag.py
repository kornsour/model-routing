"""Building and validating the job DAG."""

from __future__ import annotations

import heapq
from collections.abc import Iterable

from orchestra.model import JobSpec


class DagError(ValueError):
    pass


class CycleError(DagError):
    def __init__(self, cycle: list[str]) -> None:
        super().__init__("dependency cycle: " + " -> ".join(cycle))
        self.cycle = cycle


class DAG:
    def __init__(self, specs: Iterable[JobSpec]) -> None:
        self.specs: dict[str, JobSpec] = {}
        for spec in specs:
            if spec.name in self.specs:
                raise DagError(f"duplicate job {spec.name!r}")
            self.specs[spec.name] = spec
        self._dependents: dict[str, list[str]] = {n: [] for n in self.specs}
        for spec in self.specs.values():
            for dep in dict.fromkeys(spec.deps):
                if dep not in self.specs:
                    raise DagError(f"{spec.name!r} depends on unknown job {dep!r}")
                if dep == spec.name:
                    raise CycleError([spec.name, spec.name])
                self._dependents[dep].append(spec.name)
        for deps in self._dependents.values():
            deps.sort()
        self._order = self._toposort()

    def __contains__(self, name: str) -> bool:
        return name in self.specs

    def __len__(self) -> int:
        return len(self.specs)

    def spec(self, name: str) -> JobSpec:
        return self.specs[name]

    def deps(self, name: str) -> tuple[str, ...]:
        return self.specs[name].deps

    def dependents(self, name: str) -> list[str]:
        return list(self._dependents[name])

    def topo_order(self) -> list[str]:
        """Kahn's algorithm; among jobs that are ready together, by name."""
        return list(self._order)

    def _toposort(self) -> list[str]:
        indeg = {n: len(set(s.deps)) for n, s in self.specs.items()}
        heap = [n for n, d in indeg.items() if d == 0]
        heapq.heapify(heap)
        order: list[str] = []
        while heap:
            n = heapq.heappop(heap)
            order.append(n)
            for m in self._dependents[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    heapq.heappush(heap, m)
        if len(order) != len(self.specs):
            raise CycleError(self._find_cycle(set(self.specs) - set(order)))
        return order

    def _find_cycle(self, remaining: set[str]) -> list[str]:
        start = min(remaining)
        path: list[str] = []
        seen: dict[str, int] = {}
        node = start
        while node not in seen:
            seen[node] = len(path)
            path.append(node)
            node = min(d for d in self.specs[node].deps if d in remaining)
        return path[seen[node] :] + [node]

    def ancestors(self, name: str) -> set[str]:
        out: set[str] = set()
        stack = list(self.specs[name].deps)
        while stack:
            n = stack.pop()
            if n not in out:
                out.add(n)
                stack.extend(self.specs[n].deps)
        return out

    def descendants(self, name: str) -> set[str]:
        out: set[str] = set()
        stack = list(self._dependents[name])
        while stack:
            n = stack.pop()
            if n not in out:
                out.add(n)
                stack.extend(self._dependents[n])
        return out
