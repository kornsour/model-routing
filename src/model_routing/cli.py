"""``model-routing`` command line.

model-routing smoke  [--provider claude_cli|codex_cli] [--model M]
model-routing estimate experiments/llm/exp01_baselines.toml
model-routing run      experiments/llm/exp01_baselines.toml [--limit N] [--budget-usd X]
model-routing report   results/<experiment>/<run>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from model_routing.config import load_config
from model_routing.pricing import PriceTable
from model_routing.providers import FakeProvider, make_provider
from model_routing.providers.base import Provider
from model_routing.report import aggregate, write_report
from model_routing.runner import Runner


def _providers_for(cfg, fake: bool) -> dict[str, Provider]:
    names = {c.provider for c in cfg.candidates.values()}
    if fake:
        return {n: FakeProvider(floor_tokens=_floor(n)) for n in names}
    return {
        n: make_provider(n, **cfg.provider_options.get(n, {}), env=cfg.auth_for(n).child_env(n))
        for n in names
    }


def _floor(provider: str) -> int:
    # Measured 2026-09-18 with the minimal flag sets in providers/*.py.
    return {"claude_cli": 620, "codex_cli": 18500}.get(provider, 500)


def cmd_smoke(args: argparse.Namespace) -> int:
    prices = PriceTable.load()
    provider = make_provider(args.provider)
    model = args.model or {"claude_cli": "haiku", "codex_cli": "gpt-5.6-luna"}[args.provider]
    res = provider.call(model, "Reply with exactly the word OK.", effort=args.effort)
    price_model = model
    if res.resolved_model and prices.get(res.resolved_model):
        price_model = res.resolved_model
    cost = prices.cost(price_model, res.usage) if prices.get(price_model) else None
    print(
        json.dumps(
            {
                "provider": args.provider,
                "model": model,
                "resolved_model": res.resolved_model,
                "output": res.output,
                "error": res.error,
                "usage": vars(res.usage),
                "duration_ms": res.duration_ms,
                "cost_usd_list": cost,
                "cost_usd_reported": res.cost_usd_reported,
            },
            indent=2,
        )
    )
    return 0 if res.error is None else 1


def cmd_estimate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    prices = PriceTable.load()
    out = Path(args.out) / cfg.name / ("estimate-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    runner = Runner(
        cfg,
        _providers_for(cfg, fake=True),
        prices,
        out,
        limit=args.limit,
        trials=args.trials,
        sample=args.sample,
        verbose=False,
    )
    runner.run()
    stats = aggregate([o.to_dict() for o in runner.outcomes])
    print(f"\nEstimated list-price cost for {cfg.name} (fake provider, ~4 chars/token):")
    for s in stats:
        print(f"  {s.router:<24} {s.n:>3} tasks  ${s.cost:.4f} total  ${s.cost_per_task:.4f}/task")
    print(f"  {'TOTAL':<24} {'':>3}        ${runner.spent_usd:.4f}")
    print("\nOutput tokens are a flat guess; real spend depends on how much the models write.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    prices = PriceTable.load()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) / cfg.name / (("fake-" if args.fake else "") + stamp)
    runner = Runner(
        cfg,
        _providers_for(cfg, fake=args.fake),
        prices,
        out,
        budget_usd=args.budget_usd,
        limit=args.limit,
        sample=args.sample,
        trials=args.trials,
        routers_filter=tuple(args.routers.split(",")) if args.routers else None,
        cooldown_s=args.cooldown_s,
    )
    runner.run()
    md = write_report(out)
    print("\n" + md)
    print(f"report: {out / 'summary.md'}")
    if not args.fake:
        from model_routing.dashboard import write_dashboard
        from model_routing.store import index_results

        results_root = Path(args.out)
        index_results(results_root, results_root / "index.sqlite")
        page = write_dashboard(results_root / "index.sqlite", results_root / "dashboard.html")
        print(f"dashboard: {page.resolve()}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    import webbrowser

    from model_routing.dashboard import write_dashboard
    from model_routing.store import index_results

    ids = index_results(args.results, args.db)
    out = write_dashboard(args.db, args.out, include_synthetic=args.include_synthetic)
    print(f"indexed {len(ids)} run(s) into {args.db}")
    print(f"dashboard: {out.resolve()}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    print(write_report(args.run_dir))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from model_routing.server import serve

    serve(
        Path.cwd(),
        Path(args.results).resolve(),
        args.port,
        open_browser=args.open,
        page=args.page,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="model-routing", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("smoke", help="one trivial call; prints usage and cost")
    s.add_argument("--provider", default="claude_cli", choices=["claude_cli", "codex_cli"])
    s.add_argument("--model")
    s.add_argument("--effort")
    s.set_defaults(fn=cmd_smoke)

    e = sub.add_parser("estimate", help="dry-run cost estimate with the fake provider")
    e.add_argument("config")
    e.add_argument("--limit", type=int)
    e.add_argument("--sample", type=int, help="N tasks evenly spaced through the set")
    e.add_argument("--trials", type=int)
    e.add_argument("--out", default="results")
    e.set_defaults(fn=cmd_estimate)

    r = sub.add_parser("run", help="run an experiment config")
    r.add_argument("config")
    r.add_argument("--limit", type=int, help="only the first N tasks")
    r.add_argument("--sample", type=int, help="N tasks evenly spaced through the set")
    r.add_argument("--trials", type=int, help="override trials from the config")
    r.add_argument("--budget-usd", type=float, help="stop when list-price spend exceeds this")
    r.add_argument("--routers", help="comma-separated router names to run (default: all)")
    r.add_argument(
        "--cooldown-s",
        type=float,
        default=0.0,
        help="sleep between router blocks so each starts with a cold cache (>=300 for Anthropic)",
    )
    r.add_argument("--fake", action="store_true", help="use the fake provider (no spend)")
    r.add_argument("--out", default="results")
    r.set_defaults(fn=cmd_run)

    rp = sub.add_parser("report", help="(re)build summary.md/csv for a run directory")
    rp.add_argument("run_dir")
    rp.set_defaults(fn=cmd_report)

    d = sub.add_parser(
        "dashboard", help="index results/ into SQLite and write a static HTML dashboard"
    )
    d.add_argument("--results", default="results")
    d.add_argument("--db", default="results/index.sqlite")
    d.add_argument("--out", default="results/dashboard.html")
    d.add_argument(
        "--include-synthetic", action="store_true", help="also show fake-/estimate- runs"
    )
    d.add_argument("--open", action="store_true", help="open in the default browser")
    d.set_defaults(fn=cmd_dashboard)

    lab = sub.add_parser("serve", help="launch the local experiment lab")
    lab.add_argument("--port", type=int, default=8765)
    lab.add_argument("--results", default="results")
    lab.add_argument(
        "--open", action="store_true", help="open the browser once the server is ready"
    )
    lab.add_argument(
        "--page",
        default="",
        choices=["", "dispatch"],
        help="page to open with --open (default: the lab overview)",
    )
    lab.set_defaults(fn=cmd_serve)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
