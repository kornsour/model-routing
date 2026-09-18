"""Routing strategies.  Each is a small class so a config can name it by ``kind``.

* static      - one candidate for everything (the baselines: all-cheap, all-frontier,
                and the frontier model at low effort, which is the comparison the
                cost-optimization literature says to run *before* multi-model routing)
* oracle      - route by the task's human difficulty label.  Not deployable; it is
                the upper bound on what any difficulty-based router could save.
* heuristic   - free rule-based router on prompt length / keywords / schema presence
* classifier  - a cheap model labels difficulty (structured output), then route.
                Its call is billed to the task as router overhead.
* cascade     - try candidates in order; escalate when the grader fails (the
                "re-run failures on a stronger model" pattern).  Requires a checker
                at runtime, which is the honest precondition for that pattern; the
                ``confidence`` mode instead asks the model to self-report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from model_routing.routers.base import Execute, Grade, RouteResult
from model_routing.types import Task

DIFFICULTIES = ("easy", "medium", "hard")


@dataclass
class StaticRouter:
    name: str
    candidate: str
    kind: str = "static"

    def route(self, task: Task, execute: Execute, grade: Grade) -> RouteResult:
        rec = execute(self.candidate, task, role="candidate")
        return RouteResult([rec], rec)


@dataclass
class OracleRouter:
    name: str
    map: dict[str, str]
    kind: str = "oracle"

    def route(self, task: Task, execute: Execute, grade: Grade) -> RouteResult:
        cand = self.map.get(task.difficulty) or self.map.get("default")
        if cand is None:
            raise ValueError(
                f"oracle map has no entry for difficulty {task.difficulty!r} or 'default'"
            )
        rec = execute(cand, task, role="candidate")
        return RouteResult([rec], rec, notes={"label": task.difficulty})


@dataclass
class HeuristicRouter:
    """Cheap signals only: prompt length, keyword hints, structured-output need."""

    name: str
    map: dict[str, str]
    kind: str = "heuristic"
    long_chars: int = 900
    hard_keywords: tuple[str, ...] = (
        "reconcile",
        "schedule",
        "optimi",
        "prove",
        "constraint",
        "every",
        "all of",
        "step by step",
        "compare",
        "tradeoff",
        "analy",
    )
    easy_keywords: tuple[str, ...] = (
        "classify",
        "one word",
        "yes or no",
        "label",
        "translate",
        "sentiment",
        "extract",
    )

    def label(self, task: Task) -> str:
        p = task.prompt.lower()
        if any(k in p for k in self.hard_keywords) or len(task.prompt) > self.long_chars:
            return "hard"
        if any(k in p for k in self.easy_keywords) or len(task.prompt) < 200:
            return "easy"
        return "medium"

    def route(self, task: Task, execute: Execute, grade: Grade) -> RouteResult:
        label = self.label(task)
        rec = execute(self.map.get(label, self.map["default"]), task, role="candidate")
        return RouteResult([rec], rec, notes={"label": label})


CLASSIFIER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"difficulty": {"type": "string", "enum": list(DIFFICULTIES)}},
    "required": ["difficulty"],
    "additionalProperties": False,
}

CLASSIFIER_PROMPT = (
    "You are a request router for a general-purpose assistant. Rate how much model "
    "capability the following request needs:\n"
    "- easy: one-step lookup, classification, formatting, or short rewrite\n"
    "- medium: multi-step but routine reasoning, moderate synthesis, arithmetic over a few facts\n"
    "- hard: multi-constraint reasoning, reconciliation of several sources, careful edge cases\n\n"
    "Respond with JSON only.\n\n<request>\n{prompt}\n</request>"
)


@dataclass
class ClassifierRouter:
    name: str
    classifier: str
    map: dict[str, str]
    kind: str = "classifier"
    include_context: bool = False

    def route(self, task: Task, execute: Execute, grade: Grade) -> RouteResult:
        cls_prompt = CLASSIFIER_PROMPT.format(prompt=task.prompt)
        cls = execute(
            self.classifier,
            task,
            role="router",
            prompt=cls_prompt,
            schema=CLASSIFIER_SCHEMA,
            with_context=self.include_context,
        )
        label = "medium"
        if cls.structured and cls.structured.get("difficulty") in DIFFICULTIES:
            label = str(cls.structured["difficulty"])
        else:
            m = re.search(r"\b(easy|medium|hard)\b", cls.output.lower())
            if m:
                label = m.group(1)
        rec = execute(self.map.get(label, self.map["default"]), task, role="candidate")
        return RouteResult([cls, rec], rec, notes={"label": label})


_CONFIDENCE_RE = re.compile(r"\n?\s*CONFIDENCE:\s*(high|low)\s*$", re.I)


def strip_confidence(text: str) -> str:
    """Remove the trailing CONFIDENCE line so graders see only the answer."""
    return _CONFIDENCE_RE.sub("", text).rstrip()


CONFIDENCE_SUFFIX = (
    "\n\nAfter your answer, on a final line write exactly `CONFIDENCE: high` if you are "
    "sure the answer is correct and complete, otherwise `CONFIDENCE: low`."
)


@dataclass
class CascadeRouter:
    name: str
    chain: list[str]
    kind: str = "cascade"
    escalate_on: str = "grader"  # or "confidence"
    notes: dict[str, Any] = field(default_factory=dict)

    def route(self, task: Task, execute: Execute, grade: Grade) -> RouteResult:
        calls = []
        final = None
        escalations = 0
        for i, cand in enumerate(self.chain):
            prompt = task.prompt + CONFIDENCE_SUFFIX if self.escalate_on == "confidence" else None
            rec = execute(cand, task, role="candidate", prompt=prompt)
            calls.append(rec)
            final = rec
            last = i == len(self.chain) - 1
            if last:
                break
            if self.escalate_on == "confidence":
                match = _CONFIDENCE_RE.search(rec.output)
                ok = rec.ok and match is not None and match.group(1).lower() == "high"
            else:
                ok = rec.ok and grade(task, rec)[0]
            if ok:
                break
            escalations += 1
        final_output = None
        if self.escalate_on == "confidence" and final is not None:
            final_output = strip_confidence(final.output)
        return RouteResult(calls, final, escalations=escalations, final_output=final_output)


def make_router(spec: dict[str, Any]) -> Any:
    kind = spec["kind"]
    name = spec["name"]
    if kind == "static":
        return StaticRouter(name=name, candidate=spec["candidate"])
    if kind == "oracle":
        return OracleRouter(name=name, map=dict(spec["map"]))
    if kind == "heuristic":
        return HeuristicRouter(name=name, map=dict(spec["map"]))
    if kind == "classifier":
        return ClassifierRouter(
            name=name,
            classifier=spec["classifier"],
            map=dict(spec["map"]),
            include_context=bool(spec.get("include_context", False)),
        )
    if kind == "cascade":
        return CascadeRouter(
            name=name, chain=list(spec["chain"]), escalate_on=spec.get("escalate_on", "grader")
        )
    raise ValueError(f"unknown router kind {kind!r}")
