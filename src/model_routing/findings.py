"""Turn a run's numbers into evidence for or against the routing hypotheses.

Each finding names the claim, a verdict computed from this run only, and the
numbers that produced it.  Verdicts are per run and single-trial noise
applies; the dashboard shows them next to the raw table so the reader can
disagree.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from model_routing.pricing import PriceTable
from model_routing.report import RouterStats, aggregate, pareto

SUPPORTED = "supported"
CONTRADICTED = "contradicted"
MIXED = "mixed"
INSUFFICIENT = "insufficient"

CLAIMS = {
    "F1": "Per-token price lists do not predict cost per completed task.",
    "F2": "The frontier model at low effort sits on the accuracy/cost Pareto frontier.",
    "F3": "Even perfect difficulty labels (oracle) save less than the price gap suggests.",
    "F4": (
        "Deployable routers recover only part of the oracle's saving,"
        " and a model-based router's own call is a visible cost."
    ),
    "F5": (
        "Cascades earn their saving only with a real checker; self-re"
        "ported confidence escalates too rarely."
    ),
    "F6": "Splitting one workload across models fragments the prompt cache.",
    "F7": (
        "Harness scaffolding sets a per-call token floor that differs"
        " by an order of magnitude between CLIs."
    ),
    "F8": (
        "The harness's list-price cost agrees with the CLI's reported"
        " cost (price table is current)."
    ),
}


@dataclass
class Finding:
    id: str
    claim: str
    verdict: str
    evidence: str
    numbers: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _router_specs(meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["name"]: r for r in meta.get("routers", [])}


def _candidates(meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return meta.get("candidates", {})


def _money(x: float | None) -> str:
    return "n/a" if x is None else f"${x:.4f}"


def compute_findings(meta: dict[str, Any], outcomes: list[dict[str, Any]]) -> list[Finding]:
    stats = {s.router: s for s in aggregate(outcomes)}
    specs = _router_specs(meta)
    cands = _candidates(meta)
    prices = PriceTable.load()
    front = pareto(list(stats.values()))
    out: list[Finding] = []

    statics = {n: s for n, s in stats.items() if specs.get(n, {}).get("kind") == "static"}
    routed = {
        n: s for n, s in stats.items() if specs.get(n, {}).get("kind") not in ("static", None)
    }

    # F1 - price lists vs cost per completed task
    priced = []
    for n, s in statics.items():
        c = cands.get(specs[n]["candidate"], {})
        p = prices.get(c.get("model", ""))
        if p and s.cost_per_pass is not None:
            priced.append((n, p.input, s.cost_per_pass, s.pass_rate))
    if len(priced) >= 2:
        by_price = [n for n, *_ in sorted(priced, key=lambda t: t[1])]
        by_cpp = [n for n, *_ in sorted(priced, key=lambda t: t[2])]
        same = by_price == by_cpp
        out.append(
            Finding(
                "F1",
                CLAIMS["F1"],
                CONTRADICTED if same else SUPPORTED,
                (
                    "Ranking by list input price: "
                    + " < ".join(by_price)
                    + ". Ranking by cost per completed task: "
                    + " < ".join(by_cpp)
                    + ("." if same else " (order changed).")
                ),
                {
                    n: {"input_price": p, "cost_per_pass": cpp, "pass_rate": pr}
                    for n, p, cpp, pr in priced
                },
            )
        )
    else:
        out.append(
            Finding(
                "F1",
                CLAIMS["F1"],
                INSUFFICIENT,
                "Needs at least two single-model baselines with passes.",
            )
        )

    # F2 - frontier model at low effort on the frontier
    low = [n for n in statics if cands.get(specs[n]["candidate"], {}).get("effort") == "low"]
    if low:
        on = [n for n in low if n in front]
        out.append(
            Finding(
                "F2",
                CLAIMS["F2"],
                SUPPORTED if on else CONTRADICTED,
                ", ".join(
                    f"{n}: pass {stats[n].pass_rate:.0%}, "
                    f"cost/pass {_money(stats[n].cost_per_pass)}"
                    + (" - on frontier" if n in front else " - dominated")
                    for n in low
                ),
                {"frontier": sorted(front)},
            )
        )
    else:
        out.append(
            Finding(
                "F2",
                CLAIMS["F2"],
                INSUFFICIENT,
                "No static router with effort=low in this run.",
            )
        )

    # F3 - oracle vs best single model
    oracles = [n for n in routed if specs[n]["kind"] == "oracle"]
    if oracles and statics:
        o = stats[oracles[0]]
        rivals = [
            s
            for s in statics.values()
            if s.pass_rate >= o.pass_rate and s.cost_per_pass is not None
        ]
        best = min(rivals, key=lambda s: s.cost_per_pass or 0) if rivals else None
        if o.cost_per_pass is None:
            verdict, ev = INSUFFICIENT, "Oracle completed no tasks."
        elif best is None:
            verdict = CONTRADICTED
            ev = (
                f"No single model matched the oracle's pass rate ({o.pass_rate:.0%}); "
                f"oracle cost/pass {_money(o.cost_per_pass)}."
            )
        else:
            saving = 1 - o.cost_per_pass / best.cost_per_pass if best.cost_per_pass else 0.0
            verdict = SUPPORTED if saving < 0.25 else CONTRADICTED
            ev = (
                f"Oracle cost/pass {_money(o.cost_per_pass)} vs best single model matching its "
                "pass rate "
                f"({best.router}) {_money(best.cost_per_pass)}: saving {saving:.0%}. "
                + (
                    "Under 25%: a single model is competitive even with perfect labels."
                    if saving < 0.25
                    else "Perfect labels save materially here."
                )
            )
        out.append(
            Finding(
                "F3",
                CLAIMS["F3"],
                verdict,
                ev,
                {"oracle_cost_per_pass": o.cost_per_pass},
            )
        )
    else:
        out.append(
            Finding(
                "F3",
                CLAIMS["F3"],
                INSUFFICIENT,
                "Needs an oracle router and at least one static baseline.",
            )
        )

    # F4 - deployable routers and their overhead
    deploy = [n for n in routed if specs[n]["kind"] in ("heuristic", "classifier")]
    if deploy and oracles:
        o = stats[oracles[0]]
        parts = []
        worse = 0
        for n in deploy:
            s = stats[n]
            gap = None
            if s.cost_per_pass is not None and o.cost_per_pass:
                gap = s.cost_per_pass / o.cost_per_pass - 1
                worse += int(gap > 0.05)
            ov = s.router_cost / s.cost if s.cost else 0
            parts.append(
                f"{n}: pass {s.pass_rate:.0%}, cost/pass {_money(s.cost_per_pass)}"
                + (f" ({gap:+.0%} vs oracle)" if gap is not None else "")
                + (f", router overhead {ov:.0%} of spend" if ov else "")
            )
        out.append(
            Finding(
                "F4",
                CLAIMS["F4"],
                SUPPORTED if worse == len(deploy) else (MIXED if worse else CONTRADICTED),
                "; ".join(parts),
            )
        )
    else:
        out.append(
            Finding(
                "F4",
                CLAIMS["F4"],
                INSUFFICIENT,
                "Needs heuristic/classifier routers and an oracle.",
            )
        )

    # F5 - cascades: checker vs confidence
    casc = {
        n: specs[n].get("escalate_on", "grader") for n in routed if specs[n]["kind"] == "cascade"
    }
    checker = [n for n, m in casc.items() if m == "grader"]
    conf = [n for n, m in casc.items() if m == "confidence"]
    if checker and conf:
        c, k = stats[checker[0]], stats[conf[0]]
        verdict = (
            SUPPORTED
            if c.pass_rate > k.pass_rate
            else (MIXED if c.pass_rate == k.pass_rate else CONTRADICTED)
        )
        out.append(
            Finding(
                "F5",
                CLAIMS["F5"],
                verdict,
                f"{checker[0]}: pass {c.pass_rate:.0%}, {c.escalations} escalations, "
                f"cost/pass {_money(c.cost_per_pass)}. {conf[0]}: pass {k.pass_rate:.0%}, "
                f"{k.escalations} escalations, cost/pass {_money(k.cost_per_pass)}.",
            )
        )
    elif checker or conf:
        n = (checker or conf)[0]
        s = stats[n]
        out.append(
            Finding(
                "F5",
                CLAIMS["F5"],
                INSUFFICIENT,
                f"Only one cascade ({n}): pass {s.pass_rate:.0%}, {s.escalations} escalations, "
                f"cost/pass {_money(s.cost_per_pass)}.",
            )
        )
    else:
        out.append(
            Finding(
                "F5",
                CLAIMS["F5"],
                INSUFFICIENT,
                "No cascade routers in this run.",
            )
        )

    # F6 - cache fragmentation
    multi = [n for n in routed if len(stats[n].by_candidate) > 1]
    if statics and multi:
        s_hit = sum(s.cache_hit for s in statics.values()) / len(statics)
        m_hit = sum(stats[n].cache_hit for n in multi) / len(multi)
        out.append(
            Finding(
                "F6",
                CLAIMS["F6"],
                SUPPORTED
                if s_hit > m_hit + 0.05
                else (CONTRADICTED if m_hit > s_hit + 0.05 else MIXED),
                f"Mean cache-hit share: single-model routers {s_hit:.0%} vs multi-model routers "
                f"{m_hit:.0%} ({', '.join(multi)}). Note: routers share a model's cache within its "
                "TTL unless the run used a cooldown.",
                {"static_cache_hit": s_hit, "routed_cache_hit": m_hit},
            )
        )
    else:
        out.append(
            Finding(
                "F6",
                CLAIMS["F6"],
                INSUFFICIENT,
                "Needs a single-model router and a multi-model router.",
            )
        )

    # F7 - harness floors per provider
    floors: dict[str, int] = {}
    for o in outcomes:
        for c in o["calls"]:
            u = c["usage"]
            pt = u["input_tokens"] + u["cache_read"] + u["cache_write"]
            floors[c["provider"]] = min(floors.get(c["provider"], 10**9), pt)
    if len(floors) >= 2:
        hi, lo = max(floors.values()), min(floors.values())
        out.append(
            Finding(
                "F7",
                CLAIMS["F7"],
                SUPPORTED if lo and hi / lo >= 5 else CONTRADICTED,
                "Smallest prompt seen per provider: "
                + ", ".join(f"{p} {t:,} tokens" for p, t in floors.items())
                + ".",
                floors,
            )
        )
    else:
        out.append(
            Finding(
                "F7",
                CLAIMS["F7"],
                INSUFFICIENT,
                "Smallest prompt seen: "
                + ", ".join(f"{p} {t:,} tokens" for p, t in floors.items())
                + ". Needs two providers in one run.",
            )
        )

    # F8 - price table cross-check against the CLI's own cost
    rep = [
        (o["cost_usd"], o["cost_usd_reported"])
        for o in outcomes
        if o.get("cost_usd_reported") is not None
    ]
    if rep:
        lst = sum(a for a, _ in rep)
        got = sum(b for _, b in rep)
        drift = abs(lst - got) / got if got else 0.0
        out.append(
            Finding(
                "F8",
                CLAIMS["F8"],
                SUPPORTED if drift < 0.01 else CONTRADICTED,
                f"List ${lst:.4f} vs reported ${got:.4f} over {len(rep)} outcomes "
                f"(drift {drift:.1%}).",
                {"list": lst, "reported": got},
            )
        )
    return out


def stats_for_dashboard(outcomes: list[dict[str, Any]], front: set[str]) -> list[dict[str, Any]]:
    rows = []
    for s in aggregate(outcomes):
        rows.append(_stats_row(s, s.router in front))
    return rows


def _stats_row(s: RouterStats, on_front: bool) -> dict[str, Any]:
    return {
        "router": s.router,
        "n": s.n,
        "passes": s.passes,
        "pass_rate": s.pass_rate,
        "cost": s.cost,
        "cost_per_task": s.cost_per_task,
        "cost_per_pass": s.cost_per_pass,
        "router_cost": s.router_cost,
        "escalations": s.escalations,
        "cache_hit": s.cache_hit,
        "prompt_tokens": s.prompt_tokens,
        "cache_read": s.cache_read,
        "cache_write": s.cache_write,
        "output_tokens": s.output_tokens,
        "p90_cost": s.p90_cost,
        "mean_latency_ms": s.mean_latency_ms,
        "cost_reported": s.cost_reported,
        "errors": s.errors,
        "by_difficulty": {k: list(v) for k, v in s.by_difficulty.items()},
        "by_candidate": s.by_candidate,
        "pareto": on_front,
    }
