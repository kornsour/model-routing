"""Aggregate a run directory into the numbers that decide the routing question.

The headline metric is **cost per completed task** (total spend / passes),
not cost per request: a cheap model that fails and gets re-run is not cheap.
Cache economics are reported per router as the share of prompt tokens served
from cache, so cache fragmentation across models is visible directly.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RouterStats:
    router: str
    n: int
    passes: int
    cost: float
    cost_reported: float | None
    router_cost: float
    escalations: int
    prompt_tokens: int
    cache_read: int
    cache_write: int
    output_tokens: int
    reasoning: int
    latency_ms: list[float]
    costs: list[float]
    by_difficulty: dict[str, tuple[int, int]]
    by_candidate: dict[str, int]
    errors: int

    @property
    def pass_rate(self) -> float:
        return self.passes / self.n if self.n else 0.0

    @property
    def cost_per_task(self) -> float:
        return self.cost / self.n if self.n else 0.0

    @property
    def cost_per_pass(self) -> float | None:
        return self.cost / self.passes if self.passes else None

    @property
    def cache_hit(self) -> float:
        return self.cache_read / self.prompt_tokens if self.prompt_tokens else 0.0

    @property
    def p90_cost(self) -> float:
        if not self.costs:
            return 0.0
        s = sorted(self.costs)
        return s[min(len(s) - 1, int(0.9 * (len(s) - 1)))]

    @property
    def mean_latency_ms(self) -> float:
        return statistics.fmean(self.latency_ms) if self.latency_ms else 0.0


def load_outcomes(run_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / "outcomes.jsonl"
    rows = []
    with path.open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def aggregate(outcomes: list[dict[str, Any]]) -> list[RouterStats]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in outcomes:
        groups[o["router"]].append(o)
    stats = []
    for router, rows in groups.items():
        by_diff: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        by_cand: dict[str, int] = defaultdict(int)
        reported: list[float | None] = []
        errors = 0
        for o in rows:
            by_diff[o["difficulty"]][0] += 1
            by_diff[o["difficulty"]][1] += int(o["passed"])
            reported.append(o.get("cost_usd_reported"))
            for c in o["calls"]:
                if c["role"] == "candidate":
                    by_cand[c["candidate"]] += 1
                if c.get("error"):
                    errors += 1
        u = [o["usage"] for o in rows]
        stats.append(
            RouterStats(
                router=router,
                n=len(rows),
                passes=sum(int(o["passed"]) for o in rows),
                cost=sum(o["cost_usd"] for o in rows),
                cost_reported=(
                    None if any(r is None for r in reported) else sum(r for r in reported if r)
                ),
                router_cost=sum(o["router_cost_usd"] for o in rows),
                escalations=sum(o["escalations"] for o in rows),
                prompt_tokens=sum(
                    x["input_tokens"] + x["cache_read"] + x["cache_write"] for x in u
                ),
                cache_read=sum(x["cache_read"] for x in u),
                cache_write=sum(x["cache_write"] for x in u),
                output_tokens=sum(x["output_tokens"] for x in u),
                reasoning=sum(x["reasoning"] for x in u),
                latency_ms=[o["duration_ms"] for o in rows],
                costs=[o["cost_usd"] for o in rows],
                by_difficulty={k: (v[0], v[1]) for k, v in by_diff.items()},
                by_candidate=dict(by_cand),
                errors=errors,
            )
        )
    return sorted(stats, key=lambda s: s.cost_per_task)


def pareto(stats: list[RouterStats]) -> set[str]:
    """Routers not dominated on (higher pass rate, lower cost per task)."""
    front = set()
    for s in stats:
        dominated = any(
            (o.pass_rate >= s.pass_rate and o.cost_per_task < s.cost_per_task)
            or (o.pass_rate > s.pass_rate and o.cost_per_task <= s.cost_per_task)
            for o in stats
            if o is not s
        )
        if not dominated:
            front.add(s.router)
    return front


def candidate_table(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per (router, candidate): mean prompt size and cache hit ratio - the cache story."""
    agg: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: {
            "calls": 0,
            "prompt": 0,
            "cache_read": 0,
            "cache_write": 0,
            "cache_write_1h": 0,
            "cost": 0.0,
        }
    )
    for o in outcomes:
        for c in o["calls"]:
            u = c["usage"]
            a = agg[(o["router"], c["candidate"], c["role"])]
            a["calls"] += 1
            a["prompt"] += u["input_tokens"] + u["cache_read"] + u["cache_write"]
            a["cache_read"] += u["cache_read"]
            a["cache_write"] += u["cache_write"]
            a["cache_write_1h"] += u.get("cache_write_1h", 0)
            a["cost"] += c["cost_usd_list"]
    rows = []
    for (router, cand, role), a in sorted(agg.items()):
        rows.append(
            {
                "router": router,
                "candidate": cand,
                "role": role,
                "calls": int(a["calls"]),
                "mean_prompt_tokens": a["prompt"] / a["calls"],
                "cache_hit": a["cache_read"] / a["prompt"] if a["prompt"] else 0.0,
                "cache_write_share": a["cache_write"] / a["prompt"] if a["prompt"] else 0.0,
                "write_1h_share": a["cache_write_1h"] / a["cache_write"]
                if a["cache_write"]
                else 0.0,
                "cost": a["cost"],
            }
        )
    return rows


def _fmt_money(x: float | None) -> str:
    return "-" if x is None else f"${x:.4f}"


def render_markdown(run_dir: str | Path, outcomes: list[dict[str, Any]]) -> str:
    run_dir = Path(run_dir)
    meta = {}
    if (run_dir / "meta.json").exists():
        meta = json.loads((run_dir / "meta.json").read_text())
    stats = aggregate(outcomes)
    front = pareto(stats)
    lines = [f"# {meta.get('experiment', run_dir.name)}", ""]
    if meta.get("hypothesis"):
        lines += [f"**Hypothesis.** {meta['hypothesis']}", ""]
    lines += [
        f"Run: `{run_dir}` · tasks: {meta.get('n_tasks', '?')} · trials: {meta.get('trials', '?')} "
        f"· order: {meta.get('order', '?')} · outcomes: {len(outcomes)}",
        "",
        "## Routers (sorted by cost per task; ★ = on the accuracy/cost Pareto frontier)",
        "",
        "| router | n | pass | cost/task | cost/pass | router overhead | escalations | "
        "cache hit | p90 cost | mean latency | reported cost | errors |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in stats:
        star = "★ " if s.router in front else ""
        lines.append(
            f"| {star}{s.router} | {s.n} | {s.pass_rate:.0%} | {_fmt_money(s.cost_per_task)} | "
            f"{_fmt_money(s.cost_per_pass)} | {s.router_cost / s.cost:.0%} | {s.escalations} | "
            f"{s.cache_hit:.0%} | {_fmt_money(s.p90_cost)} | {s.mean_latency_ms / 1000:.1f}s | "
            f"{_fmt_money(s.cost_reported)} | {s.errors} |"
            if s.cost
            else f"| {star}{s.router} | {s.n} | {s.pass_rate:.0%} | - | - | - | {s.escalations} | "
            f"- | - | {s.mean_latency_ms / 1000:.1f}s | - | {s.errors} |"
        )
    diffs = sorted({d for s in stats for d in s.by_difficulty})
    if diffs:
        lines += ["", "## Pass rate by difficulty", "", "| router | " + " | ".join(diffs) + " |"]
        lines.append("|---|" + "---:|" * len(diffs))
        for s in stats:
            cells = []
            for d in diffs:
                n, p = s.by_difficulty.get(d, (0, 0))
                cells.append(f"{p}/{n}" if n else "-")
            lines.append(f"| {s.router} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Where the tokens went (per router × candidate)",
        "",
        "| router | candidate | role | calls | mean prompt tokens | cache hit "
        "| cache write share | 1h-TTL writes | cost |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in candidate_table(outcomes):
        lines.append(
            f"| {r['router']} | {r['candidate']} | {r['role']} | {r['calls']} | "
            f"{r['mean_prompt_tokens']:.0f} | {r['cache_hit']:.0%} | "
            f"{r['cache_write_share']:.0%} | {r['write_1h_share']:.0%} | {_fmt_money(r['cost'])} |"
        )
    lines += [
        "",
        "## Reading this",
        "",
        "- **cost/pass** is the number that answers 'does routing save money': spend divided by "
        "tasks actually completed correctly. A router can win on cost/task and lose here.",
        "- **cache hit** is cache-read tokens over all prompt tokens. A single-model router on a "
        "shared context should approach the context's share of the prompt; a router that splits "
        "the same context across models pays the cache write on each model and reads less.",
        "- **cache write share** is what was written to cache; **1h-TTL writes** is the part "
        "billed at 2x input (Claude Code uses the 1-hour TTL). A 'cached' workload that keeps "
        "writing is paying more, not less.",
        "- **router overhead** is the share of spend that went to the routing decision itself.",
        "- Differences of a task or two, or fractions of a cent per task, are within single-run "
        "noise. Re-run with more trials before believing a small gap.",
    ]
    return "\n".join(lines) + "\n"


def write_report(run_dir: str | Path) -> str:
    run_dir = Path(run_dir)
    outcomes = load_outcomes(run_dir)
    md = render_markdown(run_dir, outcomes)
    (run_dir / "summary.md").write_text(md)
    stats = aggregate(outcomes)
    with (run_dir / "summary.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "router",
                "n",
                "passes",
                "pass_rate",
                "cost",
                "cost_per_task",
                "cost_per_pass",
                "router_cost",
                "escalations",
                "prompt_tokens",
                "cache_read",
                "cache_write",
                "output_tokens",
                "reasoning",
                "cache_hit",
                "p90_cost",
                "mean_latency_ms",
                "cost_reported",
                "errors",
            ]
        )
        for s in stats:
            w.writerow(
                [
                    s.router,
                    s.n,
                    s.passes,
                    f"{s.pass_rate:.4f}",
                    f"{s.cost:.6f}",
                    f"{s.cost_per_task:.6f}",
                    "" if s.cost_per_pass is None else f"{s.cost_per_pass:.6f}",
                    f"{s.router_cost:.6f}",
                    s.escalations,
                    s.prompt_tokens,
                    s.cache_read,
                    s.cache_write,
                    s.output_tokens,
                    s.reasoning,
                    f"{s.cache_hit:.4f}",
                    f"{s.p90_cost:.6f}",
                    f"{s.mean_latency_ms:.0f}",
                    "" if s.cost_reported is None else f"{s.cost_reported:.6f}",
                    s.errors,
                ]
            )
    return md
