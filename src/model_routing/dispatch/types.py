"""Shared contract for dispatch-time routing (agentic, multi-turn sessions).

See ``docs/experiments/dispatch-routing.md``.  The single-shot harness
(``model_routing.runner``) measures one call per task; this package measures
one or more *agent sessions* per task, each of which may run many turns with
tools inside a sandbox copy of a fixture repo.

Module ownership (keep imports pointing at this file, not at each other,
wherever possible):

* ``types``      - this file: dataclasses + protocols (the contract)
* ``agents``     - AgentProvider implementations: claude, codex, fake
* ``tasks``      - ``load_agent_tasks`` + fixture repos under ``tasks/agentic``
* ``sandbox``    - create/teardown a sandbox copy of a task repo
* ``grading``    - deterministic grading of a finished sandbox
* ``policies``   - A, A_switch, B, C1, C2, D, static
* ``runner``     - ``run_dispatch`` / ``estimate_dispatch``
* ``report``     - ``summarize`` -> summary.json + summary.md (stats, verdicts)
* ``harvest``    - scan local Claude Code transcripts for spawned task chips
* ``web``        - the local web app page + JSON API for dispatch runs
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from model_routing.types import Usage

SessionRole = Literal["setup", "worker", "router", "escalation"]
"""``setup`` seeds a parent session (sunk cost, excluded from headline);
``router`` picks a model; ``worker`` does the task; ``escalation`` is a
cascade retry on a stronger model.  All but ``setup`` count toward cost per
completed task."""

HEADLINE_ROLES: tuple[SessionRole, ...] = ("worker", "router", "escalation")


@dataclass(frozen=True)
class AgentTask:
    """One chip-shaped unit of agentic work plus how to grade it.

    ``repo`` is a fixture directory copied into a fresh sandbox per run.
    ``brief`` is what a good spawner writes (self-contained); ``brief_terse``
    is a title-level brief for the brief-quality hypothesis.
    ``parent_context`` is the prior conversation a parent session would hold
    (used to seed policies that resume a parent).  ``grader`` example::

        {"hidden_tests": "tasks/agentic/hidden/<id>",   # copied in after the run
         "visible_cmd": ["python", "-m", "pytest", "-q", "tests"],
         "allowed_paths": ["src/invoice/*.py", "tests/*.py"]}

    ``difficulty`` is a human label (easy|medium|hard) used only by the
    report; no policy may read it.
    """

    id: str
    title: str
    brief: str
    brief_terse: str
    parent_context: str
    repo: Path
    grader: dict[str, Any]
    difficulty: str = "unknown"
    category: str = "general"
    max_turns: int = 30
    tags: tuple[str, ...] = ()


@dataclass
class AgentResult:
    """What an AgentProvider returns for one session (all turns)."""

    output: str
    usage: Usage
    duration_ms: int
    num_turns: int = 0
    tool_calls: int = 0
    session_id: str | None = None
    resolved_model: str | None = None
    cost_usd_reported: float | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None


class AgentProvider(Protocol):
    """Runs one agent session with tools, confined to ``workdir``.

    ``resume_session`` continues an existing session (policies A / A_switch /
    C1); ``fork`` makes the resumed session a new id so the parent can be
    reused.  ``model`` may differ from the resumed session's model: that is
    the mid-session switch.  Implementations must never touch files outside
    ``workdir`` and must honour ``max_budget_usd`` where the CLI supports it.
    """

    name: str

    def run(
        self,
        model: str,
        prompt: str,
        *,
        workdir: Path,
        system: str | None = None,
        effort: str | None = None,
        max_turns: int = 30,
        resume_session: str | None = None,
        fork: bool = False,
        tools: bool = True,
        max_budget_usd: float = 2.0,
        timeout_s: int = 1200,
    ) -> AgentResult: ...


@dataclass
class SessionRecord:
    task_id: str
    policy: str
    trial: int
    role: SessionRole
    candidate: str
    provider: str
    model: str
    effort: str | None
    usage: Usage
    cost_usd_list: float
    duration_ms: int
    num_turns: int = 0
    tool_calls: int = 0
    session_id: str | None = None
    resumed_from: str | None = None
    cost_usd_reported: float | None = None
    resolved_model: str | None = None
    error: str | None = None
    output: str = ""
    seq: int = 0
    started_at: float = field(default_factory=time.time)
    raw: dict[str, Any] | None = None
    cost_usd_billed: float | None = None
    """Headline cost when it differs from ``cost_usd_list``.  Only the inline
    router (``C1_inline``) sets it: the whole turn is recorded in ``usage`` /
    ``cost_usd_list``, but only the *marginal* tokens the model choice added
    are billed to the task (see ``policies._policy_c1_inline``)."""

    @property
    def headline_cost_usd(self) -> float:
        return self.cost_usd_list if self.cost_usd_billed is None else self.cost_usd_billed

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["usage"] = asdict(self.usage)
        d["headline_cost_usd"] = self.headline_cost_usd
        return d


@dataclass
class GradeResult:
    passed: bool
    checks: dict[str, bool]
    detail: str = ""
    files_changed: list[str] = field(default_factory=list)


@dataclass
class DispatchOutcome:
    task_id: str
    policy: str
    trial: int
    sessions: list[SessionRecord]
    grade: GradeResult
    difficulty: str = "unknown"
    category: str = "general"
    chosen_candidate: str | None = None
    escalations: int = 0
    router_fallback: bool = False
    """The router produced no usable pick (e.g. the parent tried to use a tool in
    a tools-off turn) and the policy fell back to the parent model.  Reported per
    policy; it biases a routing policy toward ``B``, never away from it."""
    cascade_checks: list[dict[str, Any]] = field(default_factory=list)
    """Cascade (D) only: one entry per non-final attempt with the candidate, the
    escalation checker's verdict and reason, so a run can show *why* a cascade
    did or did not escalate."""

    @property
    def passed(self) -> bool:
        return self.grade.passed

    @property
    def cost_usd(self) -> float:
        """Headline cost: everything except parent-session setup.  A session
        with ``cost_usd_billed`` set contributes that instead of its full list
        cost (inline router turns)."""
        return sum(s.headline_cost_usd for s in self.sessions if s.role in HEADLINE_ROLES)

    @property
    def cost_usd_full(self) -> float:
        """Every headline-role session at its full list cost (no marginal billing)."""
        return sum(s.cost_usd_list for s in self.sessions if s.role in HEADLINE_ROLES)

    @property
    def errors(self) -> int:
        """Sessions that ended with a provider error (timeout, budget cap, exit code).
        They are still graded and counted - intention to treat - but reported."""
        return sum(1 for s in self.sessions if s.role in HEADLINE_ROLES and s.error)

    @property
    def setup_cost_usd(self) -> float:
        return sum(s.cost_usd_list for s in self.sessions if s.role == "setup")

    @property
    def router_cost_usd(self) -> float:
        return sum(s.headline_cost_usd for s in self.sessions if s.role == "router")

    @property
    def turns(self) -> int:
        return sum(s.num_turns for s in self.sessions if s.role in HEADLINE_ROLES)

    @property
    def duration_ms(self) -> int:
        return sum(s.duration_ms for s in self.sessions if s.role in HEADLINE_ROLES)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "policy": self.policy,
            "trial": self.trial,
            "passed": self.passed,
            "checks": self.grade.checks,
            "grade_detail": self.grade.detail,
            "files_changed": self.grade.files_changed,
            "difficulty": self.difficulty,
            "category": self.category,
            "chosen_candidate": self.chosen_candidate,
            "escalations": self.escalations,
            "router_fallback": self.router_fallback,
            "cascade_checks": self.cascade_checks,
            "cost_usd": self.cost_usd,
            "cost_usd_full": self.cost_usd_full,
            "errors": self.errors,
            "setup_cost_usd": self.setup_cost_usd,
            "router_cost_usd": self.router_cost_usd,
            "turns": self.turns,
            "duration_ms": self.duration_ms,
            "sessions": [s.to_dict() for s in self.sessions],
        }


@dataclass
class Progress:
    """Emitted by the runner after every session; the web app polls it."""

    run_dir: str
    state: Literal["running", "paused", "done", "failed", "over_budget", "cancelled"]
    total: int  # planned (task, policy, trial) cells
    done: int
    spent_usd: float
    budget_usd: float | None
    current: str = ""  # e.g. "fix-pagination · C1 · trial 1 · worker(sonnet)"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
