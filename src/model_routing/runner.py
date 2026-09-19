"""Run an experiment: every router over every task, recording every call.

Ordering matters for caching and is therefore explicit:

* ``by_router`` (default): all tasks for router A, then all for router B.  A
  single-model router keeps its prompt cache warm across tasks; a routed run
  fragments the cache across models.  This is the fair way to compare routers
  as deployed systems.
* ``by_task``: for each task, run every router before moving on.  This
  interleaves models and is a pessimistic caching scenario for everyone.

Calls are appended to ``calls.jsonl`` as they happen so an interrupted or
over-budget run still leaves usable data.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model_routing import __version__
from model_routing.config import ExperimentConfig
from model_routing.graders import grade as grade_spec
from model_routing.pricing import PriceTable, embedded_list_cost
from model_routing.providers.base import Provider
from model_routing.routers import make_router
from model_routing.tasks import ContextStore, load_tasks
from model_routing.types import CallRecord, Outcome, Role, Task


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Runner:
    cfg: ExperimentConfig
    providers: dict[str, Provider]
    prices: PriceTable
    out_dir: Path
    budget_usd: float | None = None
    limit: int | None = None
    sample: int | None = None
    trials: int | None = None
    routers_filter: tuple[str, ...] | None = None
    cooldown_s: float = 0.0
    """Seconds to sleep between router blocks in ``by_router`` order.  Prompt
    caches are model-scoped and shared across routers within their TTL, so a
    router that reuses a model right after another router inherits a warm
    cache.  Set >= 300 (the 5-minute TTL) to make each router start cold."""
    verbose: bool = True
    spent_usd: float = 0.0
    seq: int = 0
    outcomes: list[Outcome] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.tasks = load_tasks(
            self.cfg.tasks,
            limit=self.limit or self.cfg.limit,
            sample=self.sample,
            tags=self.cfg.tags,
        )
        self.contexts = ContextStore(self.cfg.tasks.parent)
        self.routers = [
            make_router(r)
            for r in self.cfg.routers
            if not self.routers_filter or r["name"] in self.routers_filter
        ]
        if not self.routers:
            raise ValueError(f"no routers selected (filter={self.routers_filter})")
        self._calls_fh = (self.out_dir / "calls.jsonl").open("a")
        self._outcomes_fh = (self.out_dir / "outcomes.jsonl").open("a")
        self._check_prices()
        self._write_meta()

    # -- setup -------------------------------------------------------------
    def _check_prices(self) -> None:
        missing = [
            c.model for c in self.cfg.candidates.values() if self.prices.get(c.model) is None
        ]
        if missing:
            raise ValueError(f"no price rows for candidate models: {missing}")

    def _write_meta(self) -> None:
        if self.cfg.source:
            shutil.copy(self.cfg.source, self.out_dir / "config.toml")
        context_hashes = {}
        for name in sorted({task.context for task in self.tasks if task.context}):
            context = self.cfg.tasks.parent / "context" / name
            context_hashes[name] = hashlib.sha256(context.read_bytes()).hexdigest()
        meta = {
            "task_sha256": hashlib.sha256(self.cfg.tasks.read_bytes()).hexdigest(),
            "context_sha256": context_hashes,
            "task_manifest": [
                {
                    "id": task.id,
                    "difficulty": task.difficulty,
                    "category": task.category,
                    "context": task.context,
                    "grader_type": task.grader.get("type"),
                }
                for task in self.tasks
            ],
            "pricing": {m: vars(self.prices.get(m)) for m in self.prices.models()},
            "experiment": self.cfg.name,
            "hypothesis": self.cfg.hypothesis,
            "started_at": datetime.now(UTC).isoformat(),
            "harness_version": __version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "tasks": str(self.cfg.tasks),
            "n_tasks": len(self.tasks),
            "trials": self.trials or self.cfg.trials,
            "order": self.cfg.order,
            "budget_usd": self.budget_usd,
            "providers": {name: _tool_version(name) for name in self.providers},
            "candidates": {k: vars(v) for k, v in self.cfg.candidates.items()},
            "routers": self.cfg.routers,
        }
        (self.out_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))

    # -- execution ---------------------------------------------------------
    def execute(
        self,
        candidate_name: str,
        task: Task,
        *,
        role: Role = "candidate",
        prompt: str | None = None,
        schema: dict[str, Any] | None = None,
        with_context: bool | None = None,
    ) -> CallRecord:
        if self.budget_usd is not None and self.spent_usd >= self.budget_usd:
            raise BudgetExceeded("budget exhausted before next call")
        cand = self.cfg.candidates[candidate_name]
        provider = self.providers[cand.provider]
        if with_context is None:
            with_context = role == "candidate"
        system = self.contexts.get(task.context) if with_context else None
        if schema is None and role == "candidate":
            schema = task.schema
        self.seq += 1
        started = time.time()
        res = provider.call(
            cand.model,
            prompt or task.prompt,
            system=system,
            effort=cand.effort,
            schema=schema,
            extra=cand.extra,
        )
        price_model = cand.model
        if res.resolved_model and self.prices.get(res.resolved_model):
            price_model = res.resolved_model
        cost = self.prices.cost(price_model, res.usage)
        rec = CallRecord(
            task_id=task.id,
            candidate=candidate_name,
            provider=cand.provider,
            model=cand.model,
            effort=cand.effort,
            role=role,
            output=res.output,
            usage=res.usage,
            duration_ms=res.duration_ms,
            cost_usd_list=cost,
            cost_usd_reported=res.cost_usd_reported,
            structured=res.structured,
            error=res.error,
            resolved_model=res.resolved_model,
            seq=self.seq,
            started_at=started,
            raw=res.raw,
        )
        # Claude Code may make a hidden helper-model call. Its top-level usage
        # covers only the requested model, but modelUsage is a list-price ledger
        # for every model consumed by the command. Charge the whole invocation.
        cost = embedded_list_cost(rec.to_dict()) or cost
        rec.cost_usd_list = cost
        self._calls_fh.write(json.dumps(rec.to_dict(), default=str) + "\n")
        self._calls_fh.flush()
        self.spent_usd += cost
        if self.verbose:
            u = rec.usage
            print(
                f"  [{self.seq:4d}] {task.id:<22} {role:<9} {candidate_name:<14} "
                f"in={u.input_tokens:>6} cr={u.cache_read:>6} cw={u.cache_write:>5} "
                f"out={u.output_tokens:>5} ${cost:.4f} {rec.duration_ms}ms"
                + (f" ERROR: {rec.error[:60]}" if rec.error else "")
            )
        if self.budget_usd is not None and self.spent_usd > self.budget_usd:
            raise BudgetExceeded(f"spent ${self.spent_usd:.4f} > budget ${self.budget_usd:.2f}")
        return rec

    def grade(self, task: Task, rec: CallRecord, output: str | None = None) -> tuple[bool, str]:
        if not rec.ok:
            return False, f"call error: {rec.error}"
        return grade_spec(task.grader, output if output is not None else rec.output, rec.structured)

    def run_one(self, router: Any, task: Task, trial: int) -> Outcome:
        result = router.route(task, self.execute, self.grade)
        if result.final is None:
            passed, detail = False, "router produced no final call"
            final_output = ""
        else:
            final_output = (
                result.final_output if result.final_output is not None else result.final.output
            )
            passed, detail = self.grade(task, result.final, final_output)
        if result.notes:
            detail = f"{detail} | {result.notes}"
        out = Outcome(
            task_id=task.id,
            router=router.name,
            trial=trial,
            calls=result.calls,
            final_output=final_output,
            passed=passed,
            grade_detail=detail,
            difficulty=task.difficulty,
            category=task.category,
            escalations=result.escalations,
        )
        self.outcomes.append(out)
        self._outcomes_fh.write(json.dumps(out.to_dict(), default=str) + "\n")
        self._outcomes_fh.flush()
        if self.verbose:
            mark = "PASS" if passed else "FAIL"
            print(f"  {mark} {router.name}/{task.id} (${out.cost_usd:.4f})")
        return out

    def run(self) -> list[Outcome]:
        trials = self.trials or self.cfg.trials
        plan: list[tuple[Any, Task, int]] = []
        if self.cfg.order == "by_task":
            for trial in range(trials):
                for task in self.tasks:
                    for router in self.routers:
                        plan.append((router, task, trial))
        else:
            for router in self.routers:
                for trial in range(trials):
                    for task in self.tasks:
                        plan.append((router, task, trial))
        print(
            f"experiment {self.cfg.name}: {len(self.routers)} routers x {len(self.tasks)} tasks "
            f"x {trials} trials = {len(plan)} task-runs (order={self.cfg.order}) -> {self.out_dir}"
        )
        try:
            prev_router = None
            for router, task, trial in plan:
                if (
                    self.cooldown_s
                    and self.cfg.order != "by_task"
                    and prev_router is not None
                    and router is not prev_router
                ):
                    print(f"  cooldown {self.cooldown_s:.0f}s before {router.name}")
                    time.sleep(self.cooldown_s)
                prev_router = router
                self.run_one(router, task, trial)
        except BudgetExceeded as e:
            print(f"STOPPED: {e}")
        except KeyboardInterrupt:
            print("STOPPED: interrupted")
        finally:
            self._calls_fh.close()
            self._outcomes_fh.close()
        print(f"done: {len(self.outcomes)} outcomes, list-price spend ${self.spent_usd:.4f}")
        return self.outcomes


def _tool_version(provider: str) -> str | None:
    binary = {"claude_cli": "claude", "codex_cli": "codex"}.get(provider)
    if not binary or not shutil.which(binary):
        return None
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=20)
        return out.stdout.strip().splitlines()[0] if out.stdout else None
    except (subprocess.SubprocessError, OSError):
        return None
