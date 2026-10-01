"""Core data types.

A ``JobSpec`` describes a job *and* how it behaves in simulation: how long
each attempt takes and whether it succeeds.  ``outcomes[i]`` is the outcome
of attempt ``i + 1``; the last entry repeats for any later attempt.  An
outcome is ``"ok"`` or ``"fail"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class State(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCESS = "success"
    FAILED = "failed"
    UPSTREAM_FAILED = "upstream_failed"

    @property
    def terminal(self) -> bool:
        return self in (State.SUCCESS, State.FAILED, State.UPSTREAM_FAILED)


OUTCOMES = ("ok", "fail")


@dataclass(frozen=True)
class JobSpec:
    name: str
    deps: tuple[str, ...] = ()
    priority: int = 0
    resources: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    duration: float = 1.0
    outcomes: tuple[str, ...] = ("ok",)
    max_attempts: int = 1
    backoff: float = 0.0
    max_backoff: float = float("inf")

    def __post_init__(self) -> None:
        object.__setattr__(self, "deps", tuple(self.deps))
        object.__setattr__(self, "outcomes", tuple(self.outcomes))
        object.__setattr__(self, "resources", MappingProxyType(dict(self.resources)))
        if not self.name:
            raise ValueError("job name must be non-empty")
        if not self.outcomes or any(o not in OUTCOMES for o in self.outcomes):
            raise ValueError(f"{self.name}: outcomes must be a non-empty list of {OUTCOMES}")
        if self.duration < 0:
            raise ValueError(f"{self.name}: duration must be >= 0")
        if self.max_attempts < 1:
            raise ValueError(f"{self.name}: max_attempts must be >= 1")
        if any(v < 1 for v in self.resources.values()):
            raise ValueError(f"{self.name}: resource amounts must be >= 1")

    def outcome(self, attempt: int) -> str:
        return self.outcomes[min(attempt, len(self.outcomes)) - 1]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> JobSpec:
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown job fields: {sorted(unknown)}")
        return cls(**dict(data))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "deps": list(self.deps),
            "priority": self.priority,
            "resources": dict(self.resources),
            "duration": self.duration,
            "outcomes": list(self.outcomes),
            "max_attempts": self.max_attempts,
            "backoff": self.backoff,
            "max_backoff": self.max_backoff,
        }


@dataclass
class JobRun:
    """Mutable per-job state during and after a run."""

    name: str
    state: State = State.PENDING
    attempts: int = 0
    started_at: float | None = None  # start of the first attempt
    finished_at: float | None = None  # when it reached a terminal state
    retry_at: float | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "attempts": self.attempts,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "retry_at": self.retry_at,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Event:
    """One entry of a run's event log.  ``kind`` is one of ``start``,
    ``success``, ``fail``, ``retry`` (a failed attempt that will be retried;
    ``detail`` holds the retry time), ``upstream_failed``."""

    time: float
    job: str
    kind: str
    attempt: int = 0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "job": self.job,
            "kind": self.kind,
            "attempt": self.attempt,
            "detail": self.detail,
        }


@dataclass
class RunResult:
    runs: dict[str, JobRun]
    events: list[Event]
    makespan: float

    def state(self, name: str) -> State:
        return self.runs[name].state

    def by_state(self, state: State) -> list[str]:
        return sorted(n for n, r in self.runs.items() if r.state is state)
