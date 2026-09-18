"""Core data types shared by providers, routers, the runner, and the report."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Role = Literal["candidate", "router"]


@dataclass(frozen=True)
class Task:
    """One unit of work plus how to grade it.

    ``difficulty`` is a human label used by the oracle router and by the
    report; routers other than ``oracle`` never see it.  ``context`` names a
    shared document (see ``tasks/llm/context/``) that is prepended as system
    context; many tasks sharing one context is what makes prompt caching
    matter.
    """

    id: str
    prompt: str
    grader: dict[str, Any]
    difficulty: str = "unknown"
    category: str = "general"
    context: str | None = None
    schema: dict[str, Any] | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Candidate:
    """A concrete thing you can route to: provider + model + settings."""

    name: str
    provider: str
    model: str
    effort: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Usage:
    """Normalized token usage.  All fields are counts of tokens.

    ``input_tokens`` is the *uncached* input; ``cache_read`` and
    ``cache_write`` are the cached portions.  Total prompt size is the sum of
    the three.  ``cache_write_1h`` is the part of ``cache_write`` written with
    a 1-hour TTL, which Anthropic bills at 2x input instead of 1.25x; the
    Claude Code harness uses the 1-hour TTL, so this is not zero in practice.
    ``reasoning`` is included in ``output_tokens`` where the provider bills it
    that way (both CLIs do) and reported separately for analysis.
    """

    input_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0
    output_tokens: int = 0
    reasoning: int = 0
    cache_write_1h: int = 0

    @property
    def prompt_tokens(self) -> int:
        return self.input_tokens + self.cache_read + self.cache_write

    @property
    def cache_hit_ratio(self) -> float:
        total = self.prompt_tokens
        return self.cache_read / total if total else 0.0

    def add(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.cache_read + other.cache_read,
            self.cache_write + other.cache_write,
            self.output_tokens + other.output_tokens,
            self.reasoning + other.reasoning,
            self.cache_write_1h + other.cache_write_1h,
        )


@dataclass
class CallRecord:
    """One invocation of one candidate.  Router-overhead calls use role=router."""

    task_id: str
    candidate: str
    provider: str
    model: str
    effort: str | None
    role: Role
    output: str
    usage: Usage
    duration_ms: int
    cost_usd_list: float
    cost_usd_reported: float | None = None
    structured: dict[str, Any] | None = None
    error: str | None = None
    resolved_model: str | None = None
    seq: int = 0
    started_at: float = field(default_factory=time.time)
    raw: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["usage"] = asdict(self.usage)
        return d


@dataclass
class Outcome:
    """The router's full handling of one task: every call it made, and the verdict."""

    task_id: str
    router: str
    trial: int
    calls: list[CallRecord]
    final_output: str
    passed: bool
    grade_detail: str = ""
    difficulty: str = "unknown"
    category: str = "general"
    escalations: int = 0

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd_list for c in self.calls)

    @property
    def cost_usd_reported(self) -> float | None:
        vals = [c.cost_usd_reported for c in self.calls]
        if any(v is None for v in vals):
            return None
        return sum(v for v in vals if v is not None)

    @property
    def router_cost_usd(self) -> float:
        return sum(c.cost_usd_list for c in self.calls if c.role == "router")

    @property
    def duration_ms(self) -> int:
        return sum(c.duration_ms for c in self.calls)

    @property
    def usage(self) -> Usage:
        total = Usage()
        for c in self.calls:
            total = total.add(c.usage)
        return total

    @property
    def final_candidate(self) -> str | None:
        for c in reversed(self.calls):
            if c.role == "candidate":
                return c.candidate
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "router": self.router,
            "trial": self.trial,
            "passed": self.passed,
            "grade_detail": self.grade_detail,
            "difficulty": self.difficulty,
            "category": self.category,
            "escalations": self.escalations,
            "final_candidate": self.final_candidate,
            "cost_usd": self.cost_usd,
            "cost_usd_reported": self.cost_usd_reported,
            "router_cost_usd": self.router_cost_usd,
            "duration_ms": self.duration_ms,
            "usage": asdict(self.usage),
            "calls": [c.to_dict() for c in self.calls],
            "final_output": self.final_output,
        }
