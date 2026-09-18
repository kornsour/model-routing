"""Router protocol.

A router receives a task and an ``execute`` callback and returns the list of
calls it made plus the final answer.  Routers never touch providers directly;
the runner owns execution, pricing, ordering, and recording so every router is
measured the same way.  Router-overhead calls (a classifier) are executed via
``execute(..., role="router")`` so their cost lands on the task's bill.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from model_routing.types import CallRecord, Role, Task

Execute = Callable[..., CallRecord]
"""execute(candidate_name, task, *, role="candidate", prompt=None, schema=None) -> CallRecord"""

Grade = Callable[[Task, CallRecord], tuple[bool, str]]


@dataclass
class RouteResult:
    calls: list[CallRecord]
    final: CallRecord | None
    escalations: int = 0
    notes: dict[str, Any] = field(default_factory=dict)
    final_output: str | None = None
    """Text to grade instead of ``final.output`` (e.g. with a router-added
    confidence line stripped).  ``final.output`` stays the raw model text."""


class Router(Protocol):
    name: str
    kind: str

    def route(self, task: Task, execute: Execute, grade: Grade) -> RouteResult: ...


def _call(
    execute: Execute, candidate: str, task: Task, role: Role = "candidate", **kw: Any
) -> CallRecord:
    return execute(candidate, task, role=role, **kw)
