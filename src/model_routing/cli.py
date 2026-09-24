"""``model-routing`` command line.

model-routing smoke  [--provider claude_cli|codex_cli] [--model M]
model-routing estimate experiments/llm/exp01_baselines.toml
model-routing run      experiments/llm/exp01_baselines.toml [--limit N] [--budget-usd X]
model-routing report   results/<experiment>/<run>
model-routing dispatch-estimate experiments/agentic/exp05_dispatch.toml
model-routing dispatch-run      experiments/agentic/exp05_dispatch.toml --budget-usd X
model-routing dispatch-report   results/<experiment>/<run>
model-routing dispatch-paper    results/<experiment>/<run> [more runs] [--out draft.md]
model-routing harvest-chips
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
    from model_routing.backup import auto_backup

    auto_backup(out)
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


def cmd_dispatch_estimate(args: argparse.Namespace) -> int:
    from model_routing.dispatch.runner import estimate_dispatch, load_dispatch_config

    cfg = load_dispatch_config(args.config)
    est = estimate_dispatch(
        cfg, sample=args.sample, trials=args.trials, policies=_split(args.policies)
    )
    print(f"Dispatch estimate for {cfg.name} ({est['cells']} cells, {est['sessions']} sessions):")
    print(f"  low  ${est['usd_low']:.2f}")
    print(f"  mid  ${est['usd_mid']:.2f}")
    print(f"  high ${est['usd_high']:.2f}")
    print("  by policy (mid):")
    for name, usd in sorted(est["by_policy"].items(), key=lambda kv: -kv[1]):
        print(f"    {name:<20} ${usd:.2f}")
    print("\nAssumptions:")
    for a in est["assumptions"]:
        print(f"  - {a}")
    return 0


def cmd_dispatch_run(args: argparse.Namespace) -> int:
    from model_routing.dispatch.runner import estimate_dispatch, load_dispatch_config, run_dispatch

    cfg = load_dispatch_config(args.config)
    policies = _split(args.policies)
    est = estimate_dispatch(cfg, sample=args.sample, trials=args.trials, policies=policies)
    print(
        f"Estimate before spending: ${est['usd_low']:.2f}-${est['usd_high']:.2f} "
        f"(mid ${est['usd_mid']:.2f}) over {est['sessions']} sessions. "
        f"Budget: ${args.budget_usd:.2f}."
    )
    if args.resume:
        out = Path(args.resume)
        print(f"Resuming {out}: cells already in outcomes.jsonl are skipped.")
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = Path(args.out) / cfg.name / (("fake-" if args.fake else "") + stamp)
    run_dispatch(
        cfg,
        out_dir=out,
        budget_usd=args.budget_usd,
        sample=args.sample,
        trials=args.trials,
        policies=policies,
        fake=args.fake,
        keep_sandboxes=args.keep_sandboxes,
        resume=bool(args.resume),
    )
    from model_routing.dispatch.report import summarize

    summary = summarize(out)
    print(f"\n{summary['headline']}")
    print(f"summary: {out / 'summary.md'}")
    from model_routing.backup import auto_backup

    auto_backup(out)
    return 0


def cmd_dispatch_report(args: argparse.Namespace) -> int:
    from model_routing.dispatch.report import summarize

    summary = summarize(args.run_dir)
    print(summary["headline"])
    print(f"summary: {Path(args.run_dir) / 'summary.md'}")
    return 0


def cmd_dispatch_paper(args: argparse.Namespace) -> int:
    from datetime import date

    from model_routing.dispatch.paper import render_paper

    default = f"docs/experiments/findings/{date.today().isoformat()}-exp05-paper-draft.md"
    out = args.out or default
    path = render_paper([Path(d) for d in args.run_dirs], out=Path(out))
    print(f"paper draft: {path}")
    return 0


def cmd_dispatch_calibration(args: argparse.Namespace) -> int:
    from model_routing.dispatch.calibration import (
        calibration_table,
        relabel_tasks,
        render_calibration,
    )

    table = calibration_table(list(args.run_dirs))
    if not table:
        print("no static/cascade outcomes found in those run directories")
        return 1
    print(render_calibration(table))
    if args.write:
        counts = relabel_tasks(args.tasks, table)
        print(
            f"relabelled {counts['relabelled']} task(s) in {args.tasks}; "
            f"{counts['unchanged']} unchanged, {counts['uncalibrated']} without data"
        )
        print("Re-run `make check`, then `dispatch-preregister` before the confirmatory run.")
    return 0


def cmd_dispatch_preregister(args: argparse.Namespace) -> int:
    from model_routing.dispatch.calibration import preregistration_block
    from model_routing.dispatch.runner import load_dispatch_config

    cfg = load_dispatch_config(args.config)
    block = preregistration_block(cfg, n_tasks=args.n_tasks)
    if args.write:
        import tomllib

        text = Path(args.config).read_text()
        if cfg.preregistration is not None:
            print(f"{args.config} already has a [preregistration] table; refusing to overwrite.")
            print("Remove it by hand if you really intend to re-register (and say why in the doc).")
            return 1
        Path(args.config).write_text(text.rstrip("\n") + "\n\n" + block)
        tomllib.loads(Path(args.config).read_text())  # must still parse
        print(f"appended to {args.config}:\n")
    print(block)
    return 0


def cmd_harvest_chips(args: argparse.Namespace) -> int:
    from model_routing.dispatch.harvest import harvest_chips

    n = harvest_chips(Path(args.projects_dir).expanduser(), Path(args.out))
    print(f"harvested {n} task chip(s) -> {args.out}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from model_routing.backup import export_run

    zip_path = export_run(args.run_dir, args.out)
    print(f"exported: {zip_path.resolve()}")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    from model_routing.backup import Settings, backup_all, backup_run

    settings = Settings.load()
    if args.to:
        settings = Settings(backup_dir=Path(args.to), auto_backup=settings.auto_backup)
    if settings.backup_dir is None:
        print("No backup directory configured. Run: model-routing backup-config --dir DIR")
        return 1
    if args.run:
        result = backup_run(args.run, settings)
        print(json.dumps(result, indent=2))
    else:
        result = backup_all(args.results, settings)
        n_ok = sum(1 for r in result["runs"] if r.get("status") != "failed")
        n_failed = len(result["runs"]) - n_ok
        print(f"backed up {n_ok} run(s), {n_failed} failed, to {settings.backup_dir}")
        if result["index_snapshot"]:
            print(f"index snapshot: {result['index_snapshot']}")
        for r in result["runs"]:
            if r.get("status") == "failed":
                print(f"  FAILED {r['run_id']}: {r.get('error')}")
    return 0


def cmd_backup_status(args: argparse.Namespace) -> int:
    from model_routing.backup import backup_status

    rows = backup_status(args.results)
    if not rows:
        print("No runs found.")
        return 0
    for r in rows:
        state = (
            "up to date" if r["up_to_date"] else ("stale" if r["backed_up"] else "NOT backed up")
        )
        fake = " (simulated)" if r["fake"] else ""
        print(f"  {r['run_id']:<40} {state}{fake}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    from model_routing.backup import restore

    result = restore(args.backup_dir, args.results)
    print(f"restored {len(result['restored'])} run(s), reindexed {len(result['indexed'])}")
    if result["conflicts"]:
        print(f"conflicts ({len(result['conflicts'])}): local file differs from backup, kept local")
        for c in result["conflicts"]:
            print(f"  {c['run_id']}: {', '.join(c['files'])}")
    if result["corrupt_backups"]:
        print(f"corrupt backup manifests skipped: {', '.join(result['corrupt_backups'])}")
    return 0


def cmd_backup_config(args: argparse.Namespace) -> int:
    from model_routing.backup import Settings, set_auto_backup, set_backup_dir

    if args.dir is not None:
        set_backup_dir(Path(args.dir).expanduser())
    if args.auto is not None:
        set_auto_backup(args.auto == "on")
    settings = Settings.load()
    print(f"backup_dir:  {settings.backup_dir or '(none configured)'}")
    print(f"auto_backup: {settings.auto_backup}")
    if settings.detected_drive:
        print(f"detected Google Drive folder: {settings.detected_drive}")
    return 0


def _split(value: str | None) -> list[str] | None:
    return [v for v in value.split(",") if v] if value else None


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

    de = sub.add_parser("dispatch-estimate", help="dry-run cost estimate for a dispatch experiment")
    de.add_argument("config")
    de.add_argument("--sample", type=int, help="N tasks")
    de.add_argument("--trials", type=int)
    de.add_argument("--policies", help="comma-separated policy names (default: all in config)")
    de.set_defaults(fn=cmd_dispatch_estimate)

    dr = sub.add_parser("dispatch-run", help="run a dispatch experiment (agentic, sandboxed)")
    dr.add_argument("config")
    dr.add_argument(
        "--budget-usd", type=float, required=True, help="stop when list-price spend exceeds this"
    )
    dr.add_argument("--sample", type=int, help="N tasks")
    dr.add_argument("--trials", type=int)
    dr.add_argument("--policies", help="comma-separated policy names (default: all in config)")
    dr.add_argument("--fake", action="store_true", help="use the fake agent provider (no spend)")
    dr.add_argument(
        "--keep-sandboxes", action="store_true", help="do not delete sandbox copies after grading"
    )
    dr.add_argument("--out", default="results")
    dr.add_argument(
        "--resume",
        metavar="RUN_DIR",
        help="continue an existing run directory (same config, sample, trials, policies); "
        "completed cells are skipped",
    )
    dr.set_defaults(fn=cmd_dispatch_run)

    drp = sub.add_parser(
        "dispatch-report", help="(re)build summary.json/md for a dispatch run directory"
    )
    drp.add_argument("run_dir")
    drp.set_defaults(fn=cmd_dispatch_report)

    dpp = sub.add_parser(
        "dispatch-paper",
        help="render a white-paper Markdown draft from dispatch run dir(s) (pooled if several)",
    )
    dpp.add_argument("run_dirs", nargs="+", help="one or more results/<exp>/<stamp> directories")
    dpp.add_argument(
        "--out", help="output .md (default: docs/experiments/findings/<date>-exp05-paper-draft.md)"
    )
    dpp.set_defaults(fn=cmd_dispatch_paper)

    dc = sub.add_parser(
        "dispatch-calibration",
        help="measured per-task pass rates by model from calibration run(s); --write relabels",
    )
    dc.add_argument("run_dirs", nargs="+", help="one or more results/<exp>/<stamp> directories")
    dc.add_argument("--tasks", default="tasks/agentic/tasks.jsonl")
    dc.add_argument(
        "--write", action="store_true", help="rewrite difficulty labels in --tasks from the data"
    )
    dc.set_defaults(fn=cmd_dispatch_calibration)

    dp = sub.add_parser(
        "dispatch-preregister",
        help="print (or --write) the [preregistration] table freezing a config + task set",
    )
    dp.add_argument("config")
    dp.add_argument("--n-tasks", type=int, help="registered task count (default: all tasks)")
    dp.add_argument("--write", action="store_true", help="append the table to the config file")
    dp.set_defaults(fn=cmd_dispatch_preregister)

    hc = sub.add_parser(
        "harvest-chips", help="scan local Claude Code transcripts for spawned task chips"
    )
    hc.add_argument("--projects-dir", default="~/.claude/projects")
    hc.add_argument("--out", default="tasks/agentic/private/harvested.jsonl")
    hc.set_defaults(fn=cmd_harvest_chips)

    ex = sub.add_parser("export", help="zip a run directory (raw files + report.html + README)")
    ex.add_argument("run_dir")
    ex.add_argument("--out", help="directory to write the zip into (default: the run dir)")
    ex.set_defaults(fn=cmd_export)

    bk = sub.add_parser("backup", help="copy run(s) into the configured backup directory")
    bk.add_argument("--run", help="a single run dir; default backs up every run under --results")
    bk.add_argument("--to", help="override the configured backup directory for this call")
    bk.add_argument("--results", default="results")
    bk.set_defaults(fn=cmd_backup)

    bs = sub.add_parser("backup-status", help="per-run backup freshness")
    bs.add_argument("--results", default="results")
    bs.set_defaults(fn=cmd_backup_status)

    rs = sub.add_parser("restore", help="copy runs missing from results/ back in and reindex")
    rs.add_argument("backup_dir")
    rs.add_argument("--results", default="results")
    rs.set_defaults(fn=cmd_restore)

    bc = sub.add_parser("backup-config", help="show or change the backup directory / auto-backup")
    bc.add_argument("--dir", help="set the backup directory (absolute path)")
    bc.add_argument("--auto", choices=["on", "off"], help="enable/disable automatic backup")
    bc.set_defaults(fn=cmd_backup_config)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
