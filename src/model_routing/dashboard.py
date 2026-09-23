"""Single-file HTML dashboard over the SQLite index.

Everything the page needs is embedded (data as JSON, vanilla JS, inline SVG
charts), so it opens from ``file://`` with no server and no network.  Colors
follow the bundled data-viz reference palette, defined once as CSS variables
with a dark-mode set.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model_routing.findings import compute_findings, stats_for_dashboard
from model_routing.quality import compare
from model_routing.report import aggregate, candidate_table, pareto
from model_routing.store import connect, list_runs, run_outcomes


def _validity_assessment(
    meta: dict[str, Any], outcomes: list[dict[str, Any]], complete: bool, synthetic: bool
) -> dict[str, Any]:
    task_ids = {o["task_id"] for o in outcomes}
    categories = sorted({o.get("category", "unknown") for o in outcomes})
    difficulties = sorted({o.get("difficulty", "unknown") for o in outcomes})
    trials = int(meta.get("trials", 1))
    checks = [
        {
            "status": "good" if complete else "blocker",
            "title": "Complete paired execution",
            "detail": (
                "Every configured strategy has the same task/trial pairs."
                if complete
                else "The run is partial; completed subsets must not pass the decision gate."
            ),
        },
        {
            "status": "good",
            "title": "Reproducible inputs and accounting",
            "detail": (
                "Task file, context files, prices, provider versions, calls, and outcomes are "
                "recorded. New runs include per-context hashes and a task manifest."
            ),
        },
        {
            "status": "caution",
            "title": "Task order and cache state are experimental variables",
            "detail": (
                f"This run used {meta.get('order', 'unknown')} order. Strategy order is fixed, "
                "and model-scoped caches can carry across strategies; use counterbalanced "
                "replicate runs before attributing a cost difference to routing alone."
            ),
        },
        {
            "status": "caution" if len(task_ids) >= 8 else "blocker",
            "title": "Independent evidence is the task, not the trial",
            "detail": (
                f"{len(task_ids)} distinct tasks and {trials} trial(s). Repeated trials estimate "
                "run-to-run variation but do not increase workload coverage. Intervals resample "
                "whole tasks so trials remain clustered."
            ),
        },
        {
            "status": "blocker",
            "title": "No representative sampling frame or held-out evaluation",
            "detail": (
                "Evenly spaced bundled tasks are a convenience benchmark. Freeze a target-work "
                "sampling frame, tune only on development families, and evaluate once on unseen "
                "task families before generalizing to company work."
            ),
        },
        {
            "status": "blocker",
            "title": "Construct validity is incomplete for open-ended work",
            "detail": (
                "Deterministic graders are strong for exact extraction and arithmetic, but weak "
                "for usefulness, groundedness, tone, and completeness. Add blinded human review "
                "with a written rubric and adjudication for those categories."
            ),
        },
        {
            "status": "caution",
            "title": "CLI economics are a proxy",
            "detail": (
                "List-price tokens, CLI scaffolding, and local cache behavior do not establish "
                "native-product quality, contract pricing, concurrency, or production latency."
            ),
        },
    ]
    return {
        "readiness": "Simulation only" if synthetic else "Exploratory evidence only",
        "summary": (
            "Suitable for falsifying weak routing ideas and estimating benchmark economics; "
            "not sufficient for a causal, population-level, or production-rollout claim."
        ),
        "checks": checks,
        "task_count": len(task_ids),
        "categories": categories,
        "difficulties": difficulties,
        "has_task_manifest": bool(meta.get("task_manifest")),
    }


def build_payload(db_path: str | Path, include_synthetic: bool = False) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        runs = []
        for r in list_runs(conn, include_synthetic=include_synthetic):
            meta = json.loads(r["meta_json"])
            outcomes = run_outcomes(conn, r["run_id"])
            stats = aggregate(outcomes)
            front = pareto(stats)
            routers = {x["name"]: x for x in meta.get("routers", [])}
            cost_by_type = _cost_by_token_type(outcomes, meta)
            expected = (r["n_tasks"] or 0) * (r["trials"] or 1)
            complete = len(outcomes) == expected * len(routers)
            baseline = next(
                (
                    name
                    for name in ("all_strong", "all_sonnet", "all_gpt_sol", "all_opus")
                    if name in routers
                ),
                "",
            )
            runs.append(
                {
                    "quality": compare(
                        outcomes,
                        baseline,
                        expected,
                        min_quality=float(meta.get("lab_spec", {}).get("min_quality", 0.95)),
                        max_drop=float(meta.get("lab_spec", {}).get("max_drop", 0.02)),
                        min_saving=float(meta.get("lab_spec", {}).get("min_saving", 0.10)),
                        run_complete=complete,
                    )
                    if baseline
                    else [],
                    "baseline": baseline,
                    "complete": complete,
                    "validity": _validity_assessment(
                        meta, outcomes, complete, bool(r["synthetic"])
                    ),
                    "track": meta.get("lab_spec", {}).get("track", "legacy"),
                    "vendor": meta.get("lab_spec", {}).get("vendor", "legacy"),
                    "run_id": r["run_id"],
                    "experiment": r["experiment"],
                    "stamp": r["stamp"],
                    "path": r["path"],
                    "started_at": r["started_at"],
                    "hypothesis": r["hypothesis"] or "",
                    "n_tasks": r["n_tasks"],
                    "trials": r["trials"],
                    "order": r["task_order"],
                    "synthetic": bool(r["synthetic"]),
                    "providers": meta.get("providers", {}),
                    "task_sha256": meta.get("task_sha256"),
                    "context_sha256": meta.get("context_sha256", {}),
                    "task_manifest": meta.get("task_manifest", []),
                    "n_outcomes": len(outcomes),
                    "total_cost": conn.execute(
                        "SELECT COALESCE(SUM(cost_usd_list),0) FROM calls WHERE run_id=?",
                        (r["run_id"],),
                    ).fetchone()[0],
                    "routers": {n: {"kind": x.get("kind")} for n, x in routers.items()},
                    "stats": stats_for_dashboard(outcomes, front),
                    "candidates": candidate_table(outcomes),
                    "cost_by_type": cost_by_type,
                    "findings": [f.to_dict() for f in compute_findings(meta, outcomes)],
                    "outcomes": [
                        {
                            "router": o["router"],
                            "task_id": o["task_id"],
                            "trial": o["trial"],
                            "passed": o["passed"],
                            "difficulty": o["difficulty"],
                            "category": o["category"],
                            "cost_usd": o["cost_usd"],
                            "escalations": o["escalations"],
                            "final_candidate": o["final_candidate"],
                            "grade_detail": o["grade_detail"],
                            "final_output": o["final_output"],
                            "calls": [
                                {
                                    "seq": c["seq"],
                                    "candidate": c["candidate"],
                                    "model": c["resolved_model"] or c["model"],
                                    "effort": c["effort"],
                                    "role": c["role"],
                                    "usage": c["usage"],
                                    "cost": c["cost_usd_list"],
                                    "duration_ms": c["duration_ms"],
                                    "error": c["error"],
                                    "output": c["output"],
                                }
                                for c in o["calls"]
                            ],
                        }
                        for o in outcomes
                    ],
                }
            )
        return {"generated_at": datetime.now(UTC).isoformat(), "runs": runs}
    finally:
        conn.close()


def _cost_by_token_type(
    outcomes: list[dict[str, Any]], meta: dict[str, Any]
) -> dict[str, dict[str, float]]:
    """Per router: dollars split into uncached input / cache read / cache write / output."""
    from model_routing.pricing import Price, PriceTable

    prices = PriceTable.load()
    out: dict[str, dict[str, float]] = {}
    for o in outcomes:
        acc = out.setdefault(
            o["router"],
            {
                "input": 0.0,
                "cache_read": 0.0,
                "cache_write": 0.0,
                "output": 0.0,
                "auxiliary": 0.0,
            },
        )
        for c in o["calls"]:
            p = prices.get(c.get("resolved_model") or c["model"]) or prices.get(c["model"])
            snapshot = meta.get("pricing", {})
            saved = snapshot.get(c.get("resolved_model")) or snapshot.get(c["model"])
            if saved:
                p = Price(**saved)
            if p is None:
                continue
            u = c["usage"]
            w1h = u.get("cache_write_1h", 0)
            w5 = max(u["cache_write"] - w1h, 0)
            write_1h_price = p.cache_write_1h if p.cache_write_1h is not None else p.cache_write
            parts = {
                "input": u["input_tokens"] * p.input / 1e6,
                "cache_read": u["cache_read"] * p.cache_read / 1e6,
                "cache_write": (w5 * p.cache_write + w1h * write_1h_price) / 1e6,
                "output": u["output_tokens"] * p.output / 1e6,
            }
            for key, value in parts.items():
                acc[key] += value
            acc["auxiliary"] += max(c["cost_usd_list"] - sum(parts.values()), 0.0)
    return out


def render_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, default=str).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", data).replace(
        "__GENERATED__", html.escape(payload["generated_at"])
    )


def write_dashboard(
    db_path: str | Path, out_path: str | Path, include_synthetic: bool = False
) -> Path:
    payload = build_payload(db_path, include_synthetic=include_synthetic)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(payload))
    return out_path


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model routing runs</title>
<style>
:root {
  color-scheme: light;
  --surface: #fcfcfb; --surface-2: #f3f2ef; --border: #e2e1dc;
  --text: #0b0b0b; --text-2: #52514e; --text-3: #7a7974;
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100;
  --good: #0ca30c; --warn: #fab219; --serious: #ec835a; --critical: #d03b3b;
  --grid: #e8e7e3;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: #1a1a19; --surface-2: #242423; --border: #343432;
    --text: #ffffff; --text-2: #c3c2b7; --text-3: #8f8e87;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500;
    --grid: #2c2c2a;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #1a1a19; --surface-2: #242423; --border: #343432;
  --text: #ffffff; --text-2: #c3c2b7; --text-3: #8f8e87;
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500;
  --grid: #2c2c2a;
}
label { display:inline-flex; flex-direction:column; gap:6px; } input, select, button { font:inherit; color:var(--text); background:var(--surface-2); border:1px solid var(--border); border-radius:6px; padding:8px; } button { cursor:pointer; } button:disabled { opacity:.5; cursor:default; } details { margin:14px 0; } summary { cursor:pointer; } :focus-visible { outline:2px solid var(--s1); outline-offset:3px; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface); color: var(--text);
  font: 14px/1.45 -apple-system, "Segoe UI", Inter, Roboto, sans-serif; }
.wrap { max-width: 1240px; margin: 0 auto; padding: 24px 16px 64px; }
header { display: flex; flex-wrap: wrap; gap: 12px 24px; align-items: baseline; justify-content: space-between; }
h1 { font-size: 22px; margin: 0; } h2 { font-size: 17px; margin: 32px 0 10px; } h3 { font-size: 14px; margin: 18px 0 8px; color: var(--text-2); font-weight: 600; }
.muted { color: var(--text-3); } .small { font-size: 12px; }
.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.card { background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.tile .label { color: var(--text-2); font-size: 12px; } .tile .value { font-size: 28px; font-weight: 600; margin-top: 2px; }
.tile .sub { color: var(--text-3); font-size: 12px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; } th, td { padding: 6px 8px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
th { color: var(--text-2); font-weight: 600; white-space: nowrap; } td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr.click { cursor: pointer; } tr.click:hover { background: var(--surface-2); }
.pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; border: 1px solid transparent; }
.pill.supported { color: var(--good); border-color: var(--good); }
.pill.contradicted { color: var(--critical); border-color: var(--critical); }
.pill.mixed { color: var(--serious); border-color: var(--serious); }
.pill.insufficient { color: var(--text-3); border-color: var(--text-3); }
.pass { color: var(--good); font-weight: 600; } .fail { color: var(--critical); font-weight: 600; }
select, button, input { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 6px 10px; }
.toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 12px 0 4px; }
svg text { fill: var(--text-2); font-size: 11px; } svg .axis { stroke: var(--grid); stroke-width: 1; }
svg .lbl { fill: var(--text); font-size: 11px; }
.tip { position: fixed; pointer-events: none; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; font-size: 12px; box-shadow: 0 4px 14px rgba(0,0,0,.15); display: none; max-width: 320px; z-index: 10; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 12px; color: var(--text-2); margin: 6px 0 0; }
.legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; background: var(--sw); }
details { margin: 8px 0; } summary { cursor: pointer; }
pre { white-space: pre-wrap; word-break: break-word; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px; font-size: 12px; max-height: 320px; overflow: auto; }
.matrix td.cell { text-align: center; } .star { color: var(--s4); }
.page-nav { display:flex; gap:8px; margin:22px 0 10px; border-bottom:1px solid var(--border); padding-bottom:10px; }
.page-nav button.active { background:var(--text); color:var(--surface); }
[data-page-panel][hidden] { display:none; }
.check { border-left:4px solid var(--text-3); }
.check.good { border-left-color:var(--good); } .check.caution { border-left-color:var(--warn); } .check.blocker { border-left-color:var(--critical); }
.prose { max-width:880px; } .prose li { margin:6px 0; }
@media (max-width: 720px) { .tile .value { font-size: 22px; } th, td { padding: 5px 6px; } }
</style>
</head>
<body>
<div class="wrap">
<header>
  <div><h1>Model routing runs</h1><div class="muted small">Generated __GENERATED__ · from <code>results/</code> via the SQLite index · rebuild with <code>make dashboard</code></div></div>
  <div class="toolbar">
    <label>Theme <select id="theme"><option value="auto">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>
    <label>Track <select id="trackFilter"><option value="">All</option><option value="adoption">Adoption</option><option value="research">Research</option><option value="legacy">Legacy</option></select></label>
    <label>Vendor <select id="vendorFilter"><option value="">All</option><option value="anthropic">Anthropic</option><option value="openai">OpenAI</option><option value="legacy">Legacy</option></select></label>
    <label>Run <select id="runSel"></select></label>
    <label><input type="checkbox" id="showSynth"> show fake/estimate runs</label>
  </div>
</header>
<nav class="page-nav" aria-label="Report pages">
  <button type="button" data-page="overview" class="active">Overview &amp; lab</button>
  <button type="button" data-page="run">Run report</button>
  <button type="button" data-page="study">Study design</button>
</nav>
<section id="lab" data-page-panel="overview"></section>
<section id="overview" data-page-panel="overview"></section>
<section id="run" data-page-panel="run" hidden></section>
<section id="study" data-page-panel="study" hidden></section>
</div>
<div class="tip" id="tip"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const $ = (s, el=document) => el.querySelector(s);
const money = x => x == null ? '–' : '$' + x.toFixed(4);
const pct = x => x == null ? '–' : Math.round(x * 100) + '%';
const ppci = x => x ? `${(x[0]*100).toFixed(1)} to ${(x[1]*100).toFixed(1)} pp` : 'not estimable';
const pctci = x => x ? `${pct(x[0])} to ${pct(x[1])}` : 'not estimable';
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
try { $('#theme').value = localStorage.getItem('theme') || 'auto'; } catch {}
function applyTheme() { document.documentElement.dataset.theme = $('#theme').value; }
applyTheme();
$('#theme').addEventListener('change', () => { applyTheme(); try { localStorage.setItem('theme', $('#theme').value); } catch {} });
const tip = $('#tip');
function showTip(e, html) { tip.innerHTML = html; tip.style.display = 'block'; moveTip(e); }
function moveTip(e) { const x = Math.min(e.clientX + 14, window.innerWidth - 330); tip.style.left = x + 'px'; tip.style.top = (e.clientY + 14) + 'px'; }
function hideTip() { tip.style.display = 'none'; }

function showPage(name) {
  document.querySelectorAll('[data-page-panel]').forEach(el => { el.hidden = el.dataset.pagePanel !== name; });
  document.querySelectorAll('[data-page]').forEach(el => el.classList.toggle('active', el.dataset.page === name));
  try { history.replaceState(null, '', '#' + name); } catch {}
}
document.querySelectorAll('[data-page]').forEach(el => el.addEventListener('click', () => showPage(el.dataset.page)));

function visibleRuns() { const s = $('#showSynth').checked; return DATA.runs.filter(r => (s || !r.synthetic) && (!$('#trackFilter').value || r.track === $('#trackFilter').value) && (!$('#vendorFilter').value || r.vendor === $('#vendorFilter').value)); }

function renderOverview() {
  const runs = visibleRuns();
  const el = $('#overview');
  if (!runs.length) { el.innerHTML = '<p class="muted">No runs indexed yet. Run an experiment, then <code>make dashboard</code>.</p>'; return; }
  const spend = runs.reduce((a, r) => a + r.total_cost, 0);
  const outcomes = runs.reduce((a, r) => a + r.n_outcomes, 0);
  // Across runs: best cost/pass at the best pass rate, and how often each router lands on the frontier.
  const front = {};
  runs.forEach(r => r.stats.forEach(s => { if (s.pareto) front[s.router] = (front[s.router] || 0) + 1; }));
  const frontRows = Object.entries(front).sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${v} / ${runs.length}</td></tr>`).join('');
  const verdicts = {};
  runs.forEach(r => r.findings.forEach(f => { const v = verdicts[f.id] = verdicts[f.id] || {claim: f.claim, supported: 0, contradicted: 0, mixed: 0, insufficient: 0}; v[f.verdict]++; }));
  const vRows = Object.entries(verdicts).sort().map(([id, v]) =>
    `<tr><td><b>${id}</b> <span class="muted">${esc(v.claim)}</span></td>
      <td class="num"><span class="pill supported">${v.supported}</span></td><td class="num"><span class="pill contradicted">${v.contradicted}</span></td>
      <td class="num"><span class="pill mixed">${v.mixed}</span></td><td class="num"><span class="pill insufficient">${v.insufficient}</span></td></tr>`).join('');
  el.innerHTML = `
    <div class="grid">
      <div class="card tile"><div class="label">Runs indexed</div><div class="value">${runs.length}</div><div class="sub">${outcomes} task outcomes</div></div>
      <div class="card tile"><div class="label">List-price spend across runs</div><div class="value">${money(spend)}</div><div class="sub">metered against subscription allowance</div></div>
      <div class="card"><div class="label small muted">Routers most often on the Pareto frontier</div><table>${frontRows}</table></div>
    </div>
    <h2>Evidence across runs</h2>
    <div class="card"><table><thead><tr><th>Claim</th><th class="num">supported</th><th class="num">contradicted</th><th class="num">mixed</th><th class="num">insufficient</th></tr></thead><tbody>${vRows}</tbody></table>
    <p class="muted small">Counts of per-run verdicts. These exploratory counts mix workloads unless filtered. Runs can contain multiple trials; overlapping tasks are not independent evidence.</p></div>
    <h2>Run history</h2>
    <div class="card"><table><thead><tr><th>run</th><th>started</th><th class="num">tasks</th><th class="num">outcomes</th><th class="num">spend</th><th>best cost/pass at top pass rate</th><th>data</th></tr></thead><tbody>
      ${runs.map(r => { const top = Math.max(...r.stats.map(s => s.pass_rate)); const best = r.stats.filter(s => s.pass_rate === top && s.cost_per_pass != null).sort((a,b)=>a.cost_per_pass-b.cost_per_pass)[0];
        const dir = encodeURIComponent(r.run_id);
        return `<tr class="click" data-run="${esc(r.run_id)}"><td><b>${esc(r.experiment)}</b> <span class="muted">${esc(r.stamp)}</span>${r.synthetic ? ' <span class="pill insufficient">synthetic</span>' : ''}</td><td class="muted">${esc((r.started_at||'').slice(0,16).replace('T',' '))}</td><td class="num">${r.n_tasks ?? '–'}</td><td class="num">${r.n_outcomes}</td><td class="num">${money(r.total_cost)}</td><td>${best ? `${esc(best.router)} · ${money(best.cost_per_pass)} at ${pct(top)}` : '–'}</td><td class="small"><a href="/api/runs/report?dir=${dir}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Open report</a> &middot; <a href="/api/runs/export?dir=${dir}" onclick="event.stopPropagation()">Download .zip</a></td></tr>`; }).join('')}
    </tbody></table></div>`;
  el.querySelectorAll('tr.click').forEach(tr => tr.addEventListener('click', () => { $('#runSel').value = tr.dataset.run; renderRun(); showPage('run'); window.scrollTo({top:0, behavior:'smooth'}); }));
}

function paretoChart(stats) {
  const W = 560, H = 300, m = {l: 50, r: 20, t: 16, b: 40};
  const pts = stats.filter(s => s.cost_per_pass != null);
  if (!pts.length) return '<p class="muted small">No completed tasks to plot.</p>';
  const maxX = Math.max(...pts.map(p => p.cost_per_pass)) * 1.15;
  const x = v => m.l + (v / maxX) * (W - m.l - m.r);
  const y = v => m.t + (1 - v) * (H - m.t - m.b);
  let g = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Pass rate versus cost per completed task">`;
  for (let i = 0; i <= 4; i++) { const yy = y(i / 4); g += `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${yy}" y2="${yy}"/><text x="${m.l - 6}" y="${yy + 4}" text-anchor="end">${i * 25}%</text>`; }
  for (let i = 0; i <= 4; i++) { const v = maxX * i / 4, xx = x(v); g += `<text x="${xx}" y="${H - m.b + 16}" text-anchor="middle">$${v.toFixed(4)}</text>`; }
  g += `<text x="${(W + m.l) / 2}" y="${H - 6}" text-anchor="middle">cost per completed task (list price)</text>`;
  g += `<text transform="translate(12 ${(H - m.b + m.t) / 2}) rotate(-90)" text-anchor="middle">pass rate</text>`;
  const frontier = pts.filter(p => p.pareto).sort((a, b) => a.cost_per_pass - b.cost_per_pass);
  if (frontier.length > 1) g += `<polyline fill="none" stroke="var(--s1)" stroke-width="2" stroke-linejoin="round" stroke-dasharray="4 4" points="${frontier.map(p => `${x(p.cost_per_pass)},${y(p.pass_rate)}`).join(' ')}"/>`;
  // Direct labels with collision avoidance: try right, then push down in 13px steps
  // until the label box overlaps nothing already placed; draw a leader when moved.
  const placed = [];
  const fits = b => !placed.some(q => b.x < q.x + q.w && b.x + b.w > q.x && b.y < q.y + q.h && b.y + b.h > q.y);
  const order = pts.map((p, i) => i).sort((a, b) => pts[a].cost_per_pass - pts[b].cost_per_pass);
  order.forEach(i => {
    const p = pts[i]; const cx = x(p.cost_per_pass), cy = y(p.pass_rate);
    const w = p.router.length * 6.4 + 4, h = 12;
    let bx = cx + 9, by = cy - 4, tries = 0;
    while (!fits({x: bx, y: by - h + 2, w, h}) && tries < 12) { by += 13; tries++; if (bx + w > W - m.r) bx = cx - w - 9; }
    placed.push({x: bx, y: by - h + 2, w, h});
    if (tries) g += `<line x1="${cx}" y1="${cy}" x2="${bx < cx ? bx + w : bx}" y2="${by - 4}" stroke="var(--text-3)" stroke-width="1"/>`;
    g += `<circle class="pt" data-i="${i}" cx="${cx}" cy="${cy}" r="${p.pareto ? 6 : 5}" fill="${p.pareto ? 'var(--s1)' : 'var(--surface)'}" stroke="var(--s1)" stroke-width="2"/>`;
    g += `<text class="lbl" x="${bx}" y="${by}">${esc(p.router)}</text>`;
  });
  g += '</svg>';
  return g;
}

function costBars(run) {
  const rows = run.stats.map(s => ({r: s.router, n: s.n, ...(run.cost_by_type[s.router] || {})}));
  const keys = [['input', 'uncached input', 'var(--s1)'], ['cache_read', 'cache read', 'var(--s3)'], ['cache_write', 'cache write', 'var(--s2)'], ['output', 'output (incl. thinking)', 'var(--s4)'], ['auxiliary', 'provider helper models', 'var(--text-3)']];
  const max = Math.max(...rows.map(r => (r.input + r.cache_read + r.cache_write + r.output + r.auxiliary) / r.n)) || 1;
  const W = 560, bh = 18, gap = 10, m = {l: 150, r: 20, t: 8, b: 30};
  const H = m.t + rows.length * (bh + gap) + m.b;
  const x = v => m.l + (v / max) * (W - m.l - m.r);
  let g = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Cost per task by token type">`;
  for (let i = 0; i <= 4; i++) { const v = max * i / 4; g += `<line class="axis" x1="${x(v)}" x2="${x(v)}" y1="${m.t}" y2="${H - m.b}"/><text x="${x(v)}" y="${H - m.b + 14}" text-anchor="middle">$${v.toFixed(4)}</text>`; }
  rows.forEach((r, i) => {
    const yy = m.t + i * (bh + gap); let cur = 0;
    g += `<text x="${m.l - 8}" y="${yy + bh - 4}" text-anchor="end" class="lbl">${esc(r.r)}</text>`;
    keys.forEach(([k, label, col]) => { const v = (r[k] || 0) / r.n; if (v <= 0) return; const x0 = x(cur), x1 = x(cur + v); cur += v;
      g += `<rect class="seg" x="${x0 + 1}" y="${yy}" width="${Math.max(x1 - x0 - 2, 1)}" height="${bh}" rx="3" fill="${col}" data-label="${esc(label)}" data-v="${v}" data-r="${esc(r.r)}"/>`; });
  });
  g += '</svg>';
  return g + `<div class="legend">${keys.map(([k, l, c]) => `<span style="--sw:${c}">${l}</span>`).join('')}</div>`;
}

function renderRun() {
  const id = $('#runSel').value; const run = DATA.runs.find(r => r.run_id === id); const el = $('#run');
  if (!run) { el.innerHTML = ''; return; }
  const statRows = run.stats.map(s => `<tr><td>${s.pareto ? '<span class="star">★</span> ' : ''}<b>${esc(s.router)}</b> <span class="muted small">${esc(run.routers[s.router]?.kind || '')}</span></td>
    <td class="num">${s.n}</td><td class="num">${pct(s.pass_rate)}</td><td class="num">${money(s.cost_per_task)}</td><td class="num"><b>${money(s.cost_per_pass)}</b></td>
    <td class="num">${s.cost ? pct(s.router_cost / s.cost) : '–'}</td><td class="num">${s.escalations}</td><td class="num">${pct(s.cache_hit)}</td><td class="num">${money(s.p90_cost)}</td>
    <td class="num">${(s.mean_latency_ms / 1000).toFixed(1)}s</td><td class="num">${money(s.cost_reported)}</td><td class="num">${s.errors}</td></tr>`).join('');
  const diffs = [...new Set(run.stats.flatMap(s => Object.keys(s.by_difficulty)))].sort();
  const diffRows = run.stats.map(s => `<tr><td>${esc(s.router)}</td>${diffs.map(d => { const v = s.by_difficulty[d]; return `<td class="num">${v ? `${v[1]}/${v[0]}` : '–'}</td>`; }).join('')}</tr>`).join('');
  const findRows = run.findings.map(f => `<tr><td><b>${f.id}</b></td><td>${esc(f.claim)}</td><td><span class="pill ${f.verdict}">${f.verdict}</span></td><td class="small">${esc(f.evidence)}</td></tr>`).join('');
  const candRows = run.candidates.map(c => `<tr><td>${esc(c.router)}</td><td>${esc(c.candidate)}</td><td>${esc(c.role)}</td><td class="num">${c.calls}</td><td class="num">${Math.round(c.mean_prompt_tokens).toLocaleString()}</td><td class="num">${pct(c.cache_hit)}</td><td class="num">${pct(c.cache_write_share)}</td><td class="num">${pct(c.write_1h_share ?? 0)}</td><td class="num">${money(c.cost)}</td></tr>`).join('');
  // Task × router matrix
  const routers = run.stats.map(s => s.router);
  const tasks = [...new Set(run.outcomes.map(o => o.task_id))];
  const byKey = {}; run.outcomes.forEach(o => { byKey[o.task_id + '|' + o.router + '|' + o.trial] = o; });
  const trials = [...new Set(run.outcomes.map(o => o.trial))];
  const topPass = Math.max(...run.stats.map(s => s.pass_rate));
  const best = run.stats.filter(s => s.pass_rate === topPass && s.cost_per_pass != null).sort((a,b)=>a.cost_per_pass-b.cost_per_pass)[0];
  const promising = (run.quality || []).filter(q => q.status.startsWith('promising') && !q.router.startsWith('oracle') && !q.router.startsWith('answer_key')).sort((a,b)=>(b.saving??-Infinity)-(a.saving??-Infinity))[0];
  const checkCards = run.validity.checks.map(c => `<div class="card check ${esc(c.status)}"><b>${esc(c.title)}</b><p class="small muted">${esc(c.detail)}</p></div>`).join('');
  const mRows = tasks.map(t => { const any = run.outcomes.find(o => o.task_id === t); return `<tr><td><b>${esc(t)}</b> <span class="muted small">${esc(any.difficulty)} · ${esc(any.category)}</span></td>` +
    routers.map(r => trials.map(tr => { const o = byKey[t + '|' + r + '|' + tr]; if (!o) return '<td class="cell">–</td>';
      return `<td class="cell click" data-k="${esc(t + '|' + r + '|' + tr)}"><span class="${o.passed ? 'pass' : 'fail'}">${o.passed ? '✓' : '✗'}</span><div class="muted small">${money(o.cost_usd)}${o.escalations ? ' ↑' + o.escalations : ''}</div></td>`; }).join('')).join('') + '</tr>'; }).join('');
  el.innerHTML = `
    <h2>${esc(run.experiment)} <span class="muted">${esc(run.stamp)}</span></h2>
    <p class="muted small">${esc(run.hypothesis)}</p>
    <h3>Executive summary</h3>
    <div class="card prose"><p><b>${esc(run.validity.readiness)}.</b> ${esc(run.validity.summary)}</p>
      <ul><li>${best ? `<b>${esc(best.router)}</b> had the lowest cost per completed task among strategies tied at the observed top pass rate: <b>${money(best.cost_per_pass)}</b> at ${pct(topPass)}.` : 'No completed task result is available.'}</li>
      <li>${promising ? `<b>${esc(promising.router)}</b> passed the configured exploratory gate with an observed ${pct(promising.saving)} saving versus ${esc(run.baseline)}; its task-clustered 95% interval is ${pctci(promising.saving_ci)}.` : 'No deployable strategy passed the configured quality-and-savings screen in this run.'}</li>
      <li>Do not interpret repeated trials as additional independent tasks or the bundled workload as a representative employee-work sample.</li></ul></div>
    <div class="grid">
      <div class="card tile"><div class="label">Tasks × routers × trials</div><div class="value">${run.n_tasks} × ${routers.length} × ${run.trials}</div><div class="sub">order ${esc(run.order)} · ${run.n_outcomes} outcomes</div></div>
      <div class="card tile"><div class="label">Spend (list price)</div><div class="value">${money(run.total_cost)}</div><div class="sub">${Object.entries(run.providers).map(([k, v]) => `${k}: ${v || 'n/a'}`).join(' · ')}</div></div>
      <div class="card tile"><div class="label">On the frontier</div><div class="value">${run.stats.filter(s => s.pareto).map(s => esc(s.router)).join(', ') || '–'}</div><div class="sub">not dominated on pass rate and cost/task</div></div>
    </div>
    ${run.quality?.length ? `<h2>Quality-gated savings · ${esc(run.track)}</h2><details><summary>ⓘ How to read this comparison</summary><p>Matched tasks and trials against ${esc(run.baseline)}. Quality is deterministic grader pass rate, not a human quality rating. The 95% intervals resample task IDs and keep repeated trials together; they describe sensitivity to this task set, not a wider population. “Promising” means the chosen screen passed on this sample, not statistical proof. Oracle and answer-key strategies are research references. Any partial run needs a complete rerun.</p></details><div class="card" style="overflow:auto"><table><thead><tr><th>Strategy</th><th>Distinct tasks</th><th>Pairs</th><th>Pass rate</th><th>Quality change</th><th>95% task-clustered interval</th><th>Cost saving</th><th>95% task-clustered interval</th><th>New failures</th><th>Assessment</th></tr></thead><tbody>${run.quality.map(q=>`<tr><td>${esc(q.router)}</td><td class="num">${q.task_clusters}</td><td class="num">${q.paired}</td><td class="num">${pct(q.quality)}</td><td class="num">${(q.quality_delta*100).toFixed(1)} pp</td><td class="num">${ppci(q.quality_delta_ci)}</td><td class="num">${pct(q.saving)}</td><td class="num">${pctci(q.saving_ci)}</td><td class="num">${q.regressions}</td><td>${esc(q.router.startsWith('oracle') || q.router.startsWith('answer_key') ? 'Research reference · ' : '')}${esc(run.synthetic ? 'Simulation only' : q.status)}</td></tr>`).join('')}</tbody></table></div>` : ''}
    <h2>What the data says</h2>
    <div class="card"><table><thead><tr><th>#</th><th>Claim</th><th>Verdict</th><th>Evidence from this run</th></tr></thead><tbody>${findRows}</tbody></table></div>
    <h2>Routers</h2>
    <div class="grid">
      <div class="card"><h3>Pass rate vs. cost per completed task</h3>${paretoChart(run.stats)}<p class="muted small">Filled points and the dashed line are the Pareto frontier. Up and left is better.</p></div>
      <div class="card"><h3>Cost per task by token type</h3>${costBars(run)}<p class="muted small">Cache writes include the 2x-priced 1-hour-TTL writes the Claude CLI makes. Provider helper models are list-priced internal calls reported by the CLI but absent from its top-level token totals.</p></div>
    </div>
    <div class="card" style="margin-top:16px; overflow:auto"><table><thead><tr><th>router</th><th class="num">n</th><th class="num">pass</th><th class="num">cost/task</th><th class="num">cost/pass</th><th class="num">router overhead</th><th class="num">escalations</th><th class="num">cache hit</th><th class="num">p90 cost</th><th class="num">latency</th><th class="num">reported</th><th class="num">errors</th></tr></thead><tbody>${statRows}</tbody></table></div>
    <div class="grid" style="margin-top:16px">
      <div class="card"><h3>Pass rate by difficulty</h3><table><thead><tr><th>router</th>${diffs.map(d => `<th class="num">${esc(d)}</th>`).join('')}</tr></thead><tbody>${diffRows}</tbody></table></div>
      <div class="card" style="overflow:auto"><h3>Where the tokens went</h3><table><thead><tr><th>router</th><th>candidate</th><th>role</th><th class="num">calls</th><th class="num">mean prompt</th><th class="num">cache hit</th><th class="num">write share</th><th class="num">1h writes</th><th class="num">cost</th></tr></thead><tbody>${candRows}</tbody></table></div>
    </div>
    <h2>Validity and decision readiness</h2>
    <p class="prose">${esc(run.validity.summary)} The detailed study-design page explains what each control protects against and what remains required.</p>
    <div class="grid">${checkCards}</div>
    <h2>Every task, every router</h2>
    <div class="card" style="overflow:auto"><table class="matrix"><thead><tr><th>task</th>${routers.map(r => trials.map(tr => `<th class="num">${esc(r)}${trials.length > 1 ? ' t' + tr : ''}</th>`).join('')).join('')}</tr></thead><tbody>${mRows}</tbody></table>
    <p class="muted small">Click a cell to see the model's answer, the grader's reasoning, and each call's tokens.</p><div id="detail"></div></div>`;
  el.querySelectorAll('td.click').forEach(td => td.addEventListener('click', () => showDetail(byKey[td.dataset.k])));
  el.querySelectorAll('.pt').forEach(c => { const p = run.stats.filter(s => s.cost_per_pass != null)[+c.dataset.i];
    c.addEventListener('pointermove', e => showTip(e, `<b>${esc(p.router)}</b><br>pass ${pct(p.pass_rate)} · cost/pass ${money(p.cost_per_pass)}<br>cost/task ${money(p.cost_per_task)} · cache hit ${pct(p.cache_hit)}`)); c.addEventListener('pointerleave', hideTip); });
  el.querySelectorAll('.seg').forEach(s => { s.addEventListener('pointermove', e => showTip(e, `<b>${money(+s.dataset.v)}</b> per task · ${esc(s.dataset.label)}<br><span class="muted">${esc(s.dataset.r)}</span>`)); s.addEventListener('pointerleave', hideTip); });
}

function renderStudy() {
  const id = $('#runSel').value; const run = DATA.runs.find(r => r.run_id === id); const el = $('#study');
  const selected = run ? `<div class="card"><h3>Selected run: ${esc(run.experiment)} · ${esc(run.stamp)}</h3><p><span class="pill insufficient">${esc(run.validity.readiness)}</span> ${esc(run.validity.summary)}</p><p class="small muted">${run.validity.task_count} distinct tasks · categories ${esc(run.validity.categories.join(', '))} · difficulties ${esc(run.validity.difficulties.join(', '))} · ${run.trials} trial(s) · ${run.complete ? 'complete' : 'partial'}.</p></div><div class="grid" style="margin-top:16px">${run.validity.checks.map(c => `<div class="card check ${esc(c.status)}"><b>${esc(c.title)}</b><p class="small muted">${esc(c.detail)}</p></div>`).join('')}</div>` : '<p class="muted">Select a run to see its readiness assessment.</p>';
  el.innerHTML = `<h2>Study design: what this experiment can and cannot establish</h2>
    <div class="card prose"><p><b>Bottom line.</b> The setup is a sound exploratory benchmark for measuring local CLI routing economics under controlled tasks. It is not, by itself, a confirmatory study of company-wide productivity, native-product behavior, or causal savings. The platform deliberately labels that boundary instead of converting a green threshold into a rollout claim.</p></div>
    <h2>Selected-run assessment</h2>${selected}
    <h2>Why the existing controls are valuable</h2>
    <div class="card prose"><ul>
      <li><b>Matched task/trial pairs:</b> every strategy sees the same work, reducing workload-composition confounding. Comparisons are within task, not across unrelated aggregate samples.</li>
      <li><b>Cost per completed task:</b> the denominator includes failures, and router calls plus cascade retries are charged to the strategy. This prevents cheap-but-wrong requests from looking efficient.</li>
      <li><b>Deterministic graders:</b> exact tasks are repeatable and auditable; no hidden judge-model preference is introduced.</li>
      <li><b>Sequential calls and explicit order:</b> concurrency does not create an unrecorded latency/cache treatment. Order remains a factor to vary, not a nuisance to ignore.</li>
      <li><b>Full call records:</b> model identity, effort, token classes, price snapshot, provider cost, errors, latency, answers, and grading details support independent audit.</li>
      <li><b>Pre-run estimate, budget, and fingerprint:</b> the task/config/context/price state is frozen between estimate and launch in the local lab, limiting unnoticed protocol drift.</li>
      <li><b>Privileged references are labeled:</b> oracle labels and answer-key cascades measure an upper/reference bound; they are not presented as deployable routers.</li>
    </ul></div>
    <h2>Threats to validity and the corrective design</h2>
    <div class="card prose"><ol>
      <li><b>External validity — convenience workload.</b> Define the target population of work, sample real tasks across roles, categories, stakes, and lengths, and report coverage plus exclusions. Keep sensitive content protected.</li>
      <li><b>Construct validity — automated pass is not usefulness.</b> Retain deterministic checks for exact tasks. For writing and synthesis, use blinded reviewers, an anchored rubric, duplicate ratings, disagreement/adjudication reporting, and inter-rater agreement.</li>
      <li><b>Selection leakage — tuning and evaluation share task families.</b> Split by task family or source template, not random rows. Tune routing rules and thresholds on development/validation only; evaluate the frozen policy once on the held-out test set.</li>
      <li><b>Order and cache confounding.</b> Repeat complete runs with counterbalanced strategy order and prespecified warm/cold-cache regimes. A single fixed sequence cannot isolate routing from cache position effects.</li>
      <li><b>Pseudoreplication.</b> Treat task as the independent unit. Repeated trials estimate stochastic stability. The platform’s intervals resample whole task clusters rather than counting each trial as a new task.</li>
      <li><b>Small samples and multiple comparisons.</b> Set a smallest practically important quality loss and saving before testing; size the task set for that precision. Report intervals and category regressions, and avoid selecting a winner from many strategies without a confirmatory holdout.</li>
      <li><b>Proxy economics.</b> Validate the finalist in the actual product/API workflow with contract prices, concurrency, retry policy, cache rules, and tail latency. CLI results answer the CLI question only.</li>
      <li><b>Temporal drift.</b> Pin and record resolved model versions, price tables, prompts, and provider CLI versions. Rerun the frozen benchmark after material model or pricing changes.</li>
    </ol></div>
    <h2>Decision rule for credible evidence</h2>
    <div class="card prose"><p>Call a deployable strategy a candidate only when the complete paired run clears the prespecified minimum pass rate, maximum quality loss, minimum saving, and category-specific safety constraints. Call it validated only when the frozen strategy repeats that result on held-out representative task families, its task-clustered interval excludes an unacceptable quality loss, blinded human review supports open-ended quality, and native-workflow economics remain favorable. Report negative and inconclusive results; do not silently retune the test set.</p></div>`;
}

function showDetail(o) {
  const d = $('#detail'); if (!o) { d.innerHTML = ''; return; }
  d.innerHTML = `<div class="card" style="margin-top:12px">
    <div><b>${esc(o.task_id)}</b> · ${esc(o.router)} · <span class="${o.passed ? 'pass' : 'fail'}">${o.passed ? 'PASS' : 'FAIL'}</span> · ${money(o.cost_usd)} · final candidate ${esc(o.final_candidate)}</div>
    <div class="small muted" style="margin:6px 0">grader: ${esc(o.grade_detail)}</div>
    ${o.calls.map(c => `<details ${c.role === 'candidate' ? 'open' : ''}><summary>#${c.seq} ${esc(c.role)} · ${esc(c.candidate)} (${esc(c.model)}${c.effort ? ', ' + esc(c.effort) : ''}) · in ${c.usage.input_tokens} · cache read ${c.usage.cache_read} · cache write ${c.usage.cache_write} · out ${c.usage.output_tokens} (thinking ${c.usage.reasoning}) · ${money(c.cost)} · ${(c.duration_ms/1000).toFixed(1)}s${c.error ? ' · <span class="fail">' + esc(c.error) + '</span>' : ''}</summary><pre>${esc(c.output)}</pre></details>`).join('')}
  </div>`;
  d.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function fillRunSelect() {
  const sel = $('#runSel'); const cur = sel.value; sel.innerHTML = '';
  visibleRuns().forEach(r => { const o = document.createElement('option'); o.value = r.run_id; o.textContent = `${r.experiment} · ${r.stamp}${r.synthetic ? ' (synthetic)' : ''}`; sel.appendChild(o); });
  if ([...sel.options].some(o => o.value === cur)) sel.value = cur;
}
['#trackFilter','#vendorFilter'].forEach(id=>$(id).addEventListener('change',()=>{fillRunSelect();renderOverview();renderRun();renderStudy();}));
$('#runSel').addEventListener('change', () => { renderRun(); renderStudy(); });
$('#showSynth').addEventListener('change', () => { fillRunSelect(); renderOverview(); renderRun(); renderStudy(); });
fillRunSelect(); renderOverview(); renderRun(); renderStudy(); showPage(['overview','run','study'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview');
</script>
</body>
</html>
"""
