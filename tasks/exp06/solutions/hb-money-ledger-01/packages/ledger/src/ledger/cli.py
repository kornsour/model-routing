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
from toolbelt.money import format_money

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
    q = sub.add_parser("reap")
    q.add_argument("--inflight", default="inflight.json")
    args = parser.parse_args(argv)

    if args.cmd in ("price", "record"):
        result = run_store.load(args.run)
        cost = pricing.price_run(result, _specs(args.specs), load_rates(args.rates))
        total_minor, jobs_minor = cost.minor()
        if args.cmd == "price":
            for job, minor in sorted(jobs_minor.items()):
                print(f"{job:<24} {format_money(minor, 'USD')}")
            print(f"{'total':<24} {format_money(total_minor, 'USD')}")
            return 0
        status = "success" if not any(rr.state.value == "failed" for rr in result.runs.values()) else "failed"
        store.append(
            args.history,
            store.RunRecord(
                run_id=args.run_id,
                pipeline=args.pipeline,
                started_at=datetime.fromisoformat(args.started_at).astimezone(UTC),
                status=status,
                total_minor=total_minor,
                jobs_minor=jobs_minor,
            ),
        )
        return 0
    if args.cmd == "report":
        sys.stdout.write(report.monthly_report(store.load(args.history), args.month))
        return 0
    if args.cmd == "budgets":
        alerts = budget.check(store.load(args.history), budget.load_budgets(args.budgets), args.month)
        for a in alerts:
            print(
                f"OVER {a.pipeline}: {format_money(a.spent_minor, 'USD')} "
                f"of {format_money(a.budget_minor, 'USD')}"
            )
        return 1 if alerts else 0
    if args.cmd == "reap":
        for run_id in inflight.reap_stale(args.inflight, datetime.now(UTC)):
            print(f"reaped {run_id}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
