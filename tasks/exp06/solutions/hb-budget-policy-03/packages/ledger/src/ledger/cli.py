"""``ledger`` command line.

    ledger price RUN.json SPECS.json [--rates rates.json]
    ledger record RUN.json SPECS.json --pipeline P --run-id ID --started-at ISO [--history F]
    ledger report --month 2026-09 [--history F]
    ledger budgets --month 2026-09 --budgets budgets.json [--history F]
    ledger reap [--inflight F]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from orchestra import store as run_store
from orchestra.model import JobSpec

from ledger import budget, inflight, pricing, report, store
from ledger.rates import load_rates


def _specs(path: str) -> dict[str, JobSpec]:
    return {d["name"]: JobSpec.from_dict(d) for d in json.loads(Path(path).read_text())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ledger")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("price")
    p.add_argument("run")
    p.add_argument("specs")
    p.add_argument("--rates")
    r = sub.add_parser("record")
    r.add_argument("run")
    r.add_argument("specs")
    r.add_argument("--pipeline", required=True)
    r.add_argument("--run-id", required=True)
    r.add_argument("--started-at", required=True)
    r.add_argument("--rates")
    r.add_argument("--history", default="history.jsonl")
    m = sub.add_parser("report")
    m.add_argument("--month", required=True)
    m.add_argument("--history", default="history.jsonl")
    b = sub.add_parser("budgets")
    b.add_argument("--month", required=True)
    b.add_argument("--budgets", required=True)
    b.add_argument("--history", default="history.jsonl")
    bs = sub.add_parser("budget-set")
    bs.add_argument("pipeline")
    bs.add_argument("--budgets", required=True)
    bs.add_argument("--monthly-usd")
    bs.add_argument("--enforce")
    bs.add_argument("--max-run-usd")
    br = sub.add_parser("budget-reset")
    br.add_argument("--budgets", required=True)
    br.add_argument("--field", required=True)
    br.add_argument("--pipelines", required=True)
    bm = sub.add_parser("budget-summary")
    bm.add_argument("--budgets", required=True)
    bm.add_argument("--month", required=True)
    bm.add_argument("--history", default="history.jsonl")
    q = sub.add_parser("reap")
    q.add_argument("--inflight", default="inflight.json")
    args = parser.parse_args(argv)

    if args.cmd in ("price", "record"):
        result = run_store.load(args.run)
        cost = pricing.price_run(result, _specs(args.specs), load_rates(args.rates))
        if args.cmd == "price":
            for job, usd in sorted(cost.by_job.items()):
                print(f"{job:<24} ${usd:.4f}")
            print(f"{'total':<24} ${cost.total:.4f}")
            return 0
        status = "success" if not any(rr.state.value == "failed" for rr in result.runs.values()) else "failed"
        store.append(
            args.history,
            store.RunRecord(
                run_id=args.run_id,
                pipeline=args.pipeline,
                started_at=datetime.fromisoformat(args.started_at).astimezone(UTC),
                status=status,
                total_usd=cost.total,
                jobs=cost.by_job,
            ),
        )
        return 0
    if args.cmd == "report":
        sys.stdout.write(report.monthly_report(store.load(args.history), args.month))
        return 0
    if args.cmd == "budgets":
        alerts = budget.check(store.load(args.history), budget.load_budgets(args.budgets), args.month)
        for a in alerts:
            print(f"OVER {a.pipeline}: ${a.spent_usd:.2f} of ${a.budget_usd:.2f}")
        return 1 if alerts else 0
    if args.cmd == "budget-set":
        config = budget.load_budgets(args.budgets)
        entry = config["pipelines"].setdefault(args.pipeline, {})
        for field, raw in (("monthly_usd", args.monthly_usd), ("enforce", args.enforce), ("max_run_usd", args.max_run_usd)):
            if raw is None:
                continue
            if raw == "inherit":
                entry[field] = None
            elif field == "enforce":
                entry[field] = raw
            else:
                entry[field] = float(raw)
        budget.resolve(config, args.pipeline)
        budget.save_budgets(args.budgets, config)
        return 0
    if args.cmd == "budget-reset":
        config = budget.load_budgets(args.budgets)
        pipelines = [p for p in args.pipelines.split(",") if p]
        changed = budget.reset_to_inherit(config, pipelines, args.field)
        budget.save_budgets(args.budgets, config)
        print(f"reset {changed} pipeline(s)")
        return 0
    if args.cmd == "budget-summary":
        config = budget.load_budgets(args.budgets)
        universe = set(config["pipelines"]) | {r.pipeline for r in store.query(store.load(args.history), month=args.month)}
        governed = budget.governed_by_default(config, sorted(universe))
        default = float(config["defaults"]["monthly_usd"])
        print(f"default monthly budget ${default:.2f} governs {len(governed)} of {len(universe)} pipelines")
        for p in sorted(universe):
            policy = budget.resolve(config, p)
            kind = "inherited" if "monthly_usd" in policy.inherited else "override"
            print(f"{p:<24} ${policy.monthly_usd:>10.2f}  {kind}")
        return 0
    if args.cmd == "reap":
        for run_id in inflight.reap_stale(args.inflight, datetime.now(UTC)):
            print(f"reaped {run_id}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
