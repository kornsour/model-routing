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
from ledger.config import load_config
from toolbelt.iniconf import ConfigError
from ledger.rates import load_rates


def _specs(path: str) -> dict[str, JobSpec]:
    return {d["name"]: JobSpec.from_dict(d) for d in json.loads(Path(path).read_text())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ledger")
    parser.add_argument("--config")
    parser.add_argument("--system-config")
    parser.add_argument("--set", action="append", default=[], dest="overrides")
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
    r.add_argument("--history", default=None)
    m = sub.add_parser("report")
    m.add_argument("--month", required=True)
    m.add_argument("--history", default=None)
    b = sub.add_parser("budgets")
    b.add_argument("--month", required=True)
    b.add_argument("--budgets", required=True)
    b.add_argument("--history", default=None)
    q = sub.add_parser("reap")
    q.add_argument("--inflight", default=None)
    c = sub.add_parser("config")
    c.add_argument("action", choices=("show", "get", "why"))
    c.add_argument("key", nargs="?")
    args = parser.parse_args(argv)

    config = load_config(system=args.system_config, project=args.config, overrides=args.overrides)
    for attr in ("history", "inflight", "rates"):
        if hasattr(args, attr) and getattr(args, attr) is None:
            if attr == "rates" and args.cmd in ("price", "record") and not config.has("paths", "rates"):
                continue
            setattr(args, attr, config.get("paths", attr))

    if args.cmd == "config":
        if args.action == "show":
            sys.stdout.write(config.dump())
            return 0
        section, _, key = (args.key or "").partition(".")
        if not section or not key or not config.has(section, key):
            print(f"unknown config key: {args.key}", file=sys.stderr)
            return 1
        print(config.display(section, key) if args.action == "get" else config.provenance(section, key))
        return 0

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
    if args.cmd == "reap":
        for run_id in inflight.reap_stale(args.inflight, datetime.now(UTC)):
            print(f"reaped {run_id}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
