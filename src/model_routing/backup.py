"""Durable, off-repo backups of ``results/`` and one-click report export.

``results/`` is git-ignored and, for this operator, lives inside a git
worktree that can be deleted out from under it — so once a paid experiment
finishes, its data needs to land somewhere that survives that. This module:

* copies finished runs into a durable ``backup_dir`` (by default, a detected
  Google Drive for desktop folder), with a ``manifest.json`` of file hashes so
  a copy can be verified and re-verified idempotently (:func:`backup_run`,
  :func:`backup_all`);
* renders a standalone, printable HTML report for one run
  (:func:`render_report_html`) and zips a run for sharing
  (:func:`export_run`);
* restores backed-up runs into a fresh ``results/`` and rebuilds the SQLite
  index (:func:`restore`);
* reports backup freshness per run (:func:`backup_status`).

Settings (``backup_dir``, ``auto_backup``) persist outside the repo at
``~/.config/model-routing/settings.json`` so they are not lost with a deleted
worktree either. ``MODEL_ROUTING_BACKUP_DIR`` overrides the configured
directory (used by tests, and available for ad hoc overrides).

Nothing here ever deletes a file already inside ``backup_dir``.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model_routing import __version__

SETTINGS_ENV_HOME = "MODEL_ROUTING_CONFIG_HOME"
BACKUP_DIR_ENV = "MODEL_ROUTING_BACKUP_DIR"
KEEP_INDEX_SNAPSHOTS = 10


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def _config_home() -> Path:
    override = os.environ.get(SETTINGS_ENV_HOME)
    if override:
        return Path(override)
    return Path.home() / ".config" / "model-routing"


def settings_path() -> Path:
    return _config_home() / "settings.json"


def detect_drive_backup_dir() -> Path | None:
    """``~/Library/CloudStorage/GoogleDrive-<account>/My Drive`` if there's exactly one."""
    base = Path.home() / "Library" / "CloudStorage"
    if not base.is_dir():
        return None
    try:
        candidates = sorted(p for p in base.glob("GoogleDrive-*") if (p / "My Drive").is_dir())
    except OSError:
        return None
    if len(candidates) != 1:
        return None
    return candidates[0] / "My Drive" / "model-routing-backups"


@dataclass
class Settings:
    backup_dir: Path | None
    auto_backup: bool
    detected_drive: Path | None = None

    @classmethod
    def load(cls) -> Settings:
        detected = detect_drive_backup_dir()
        env_dir = os.environ.get(BACKUP_DIR_ENV)
        if env_dir:
            return cls(backup_dir=Path(env_dir), auto_backup=True, detected_drive=detected)
        path = settings_path()
        data: dict[str, Any] = {}
        if path.is_file():
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                data = {}
        raw_dir = data.get("backup_dir")
        if raw_dir:
            return cls(
                backup_dir=Path(raw_dir),
                auto_backup=bool(data.get("auto_backup", True)),
                detected_drive=detected,
            )
        return cls(backup_dir=detected, auto_backup=detected is not None, detected_drive=detected)

    def save(self) -> None:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "backup_dir": str(self.backup_dir) if self.backup_dir else None,
                    "auto_backup": self.auto_backup,
                },
                indent=2,
            )
        )


def set_backup_dir(path: Path | None, auto_backup: bool | None = None) -> Settings:
    current = Settings.load()
    if auto_backup is None:
        # Setting a directory is the operator opting in; default auto-backup on.
        auto_backup = True if path is not None else current.auto_backup
    settings = Settings(
        backup_dir=path, auto_backup=auto_backup, detected_drive=current.detected_drive
    )
    settings.save()
    return settings


def set_auto_backup(enabled: bool) -> Settings:
    current = Settings.load()
    settings = Settings(
        backup_dir=current.backup_dir, auto_backup=enabled, detected_drive=current.detected_drive
    )
    settings.save()
    return settings


# ---------------------------------------------------------------------------
# Run introspection
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def is_dispatch_run(run_dir: Path) -> bool:
    return (run_dir / "sessions.jsonl").exists()


def is_fake_run(run_dir: Path) -> bool:
    meta = _load_json(run_dir / "meta.json")
    if "fake" in meta:
        return bool(meta["fake"])
    return run_dir.name.startswith(("fake-", "estimate-"))


def run_identity(run_dir: Path) -> tuple[str, str]:
    """(experiment, stamp), matching ``store.index_run``'s ``run_id`` convention."""
    meta = _load_json(run_dir / "meta.json")
    experiment = meta.get("experiment") or run_dir.parent.name
    return str(experiment), run_dir.name


REPORTS_DIRNAME = "Reports"


def run_started_at(run_dir: Path) -> datetime:
    """When the run started, in local time: ``meta.started_at``, else the stamp
    (``20260922-233941`` local or ``20260923T025818Z`` UTC, optionally after a
    ``fake-``/``estimate-`` prefix), else the run directory's mtime."""
    meta = _load_json(run_dir / "meta.json")
    raw = meta.get("started_at")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone()
        except ValueError:
            pass
    name = run_dir.name
    for prefix in ("fake-", "estimate-"):
        name = name.removeprefix(prefix)
    for fmt, utc in (("%Y%m%dT%H%M%SZ", True), ("%Y%m%d-%H%M%S", False)):
        width = len(datetime(2000, 1, 1).strftime(fmt))
        try:
            parsed = datetime.strptime(name[:width], fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=UTC).astimezone() if utc else parsed.astimezone()
    return datetime.fromtimestamp(run_dir.stat().st_mtime).astimezone()


def export_basename(run_dir: Path) -> str:
    """``2026-09-22_23-39-41_exp05_pilot`` - sorts chronologically in a folder
    listing and says when the run happened; simulated runs are labelled."""
    experiment, _ = run_identity(run_dir)
    when = run_started_at(run_dir).strftime("%Y-%m-%d_%H-%M-%S")
    label = ""
    if run_dir.name.startswith("estimate-"):
        label = "_estimate"
    elif is_fake_run(run_dir):
        label = "_simulated"
    return f"{when}_{experiment}{label}"


def discover_all_runs(results_dir: Path) -> list[Path]:
    """Every run directory under ``results_dir``: single-shot or dispatch."""
    if not results_dir.is_dir():
        return []
    found: set[Path] = set()
    for marker in ("outcomes.jsonl", "sessions.jsonl"):
        found.update(p.parent for p in results_dir.glob(f"*/*/{marker}"))
    return sorted(found)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

_REPORT_CSS = """
:root { color-scheme: light; --bg:#fcfcfb; --bg2:#f3f2ef; --border:#e2e1dc; --text:#0b0b0b;
  --text2:#52514e; --good:#0ca30c; --warn:#c98500; --bad:#d03b3b; }
@media (prefers-color-scheme: dark) {
  :root { color-scheme: dark; --bg:#1a1a19; --bg2:#242423; --border:#343432; --text:#fff;
    --text2:#c3c2b7; }
}
* { box-sizing: border-box; }
body { margin:0; padding:24px 20px 48px; background:var(--bg); color:var(--text);
  font:14px/1.5 -apple-system,"Segoe UI",Inter,Roboto,sans-serif; max-width:960px; margin:0 auto; }
h1 { font-size:22px; margin:0 0 4px; }
h2 { font-size:16px; margin:24px 0 8px; }
.muted { color:var(--text2); }
.small { font-size:12px; }
.banner { border:2px dashed var(--warn); border-radius:8px; padding:10px 14px; font-weight:600;
  color:var(--warn); margin:12px 0; }
.headline { font-size:18px; font-weight:700; background:var(--bg2); border:1px solid var(--border);
  border-radius:8px; padding:12px 14px; margin:12px 0; }
table { border-collapse:collapse; width:100%; font-size:13px; margin:8px 0 16px; }
th, td { padding:6px 8px; border-bottom:1px solid var(--border); text-align:left;
  vertical-align:top; }
th { color:var(--text2); font-weight:600; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
.verdict-supported { color:var(--good); font-weight:600; }
.verdict-not_supported { color:var(--bad); font-weight:600; }
.verdict-inconclusive { color:var(--warn); font-weight:600; }
.meta-grid { display:grid; grid-template-columns:max-content 1fr; gap:2px 14px; font-size:13px; }
.meta-grid dt { color:var(--text2); }
.meta-grid dd { margin:0; }
pre { white-space:pre-wrap; word-break:break-word; background:var(--bg2);
  border:1px solid var(--border); border-radius:8px; padding:10px 12px; }
@media print { body { max-width:none; } .banner { border-style:solid; } }
"""


def _fmt_money(x: Any) -> str:
    try:
        return "-" if x is None else f"${float(x):.4f}"
    except (TypeError, ValueError):
        return "-"


def _fmt_pct(x: Any) -> str:
    try:
        return "-" if x is None else f"{float(x) * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def _meta_table(meta: dict[str, Any], extra: dict[str, Any]) -> str:
    rows = {
        "Started": meta.get("started_at", "unknown"),
        "Harness version": meta.get("harness_version", __version__),
        "Git SHA": meta.get("git_sha") or "not recorded",
        "Python": meta.get("python", "unknown"),
        "Config hash": meta.get("config_sha256") or meta.get("task_sha256") or "not recorded",
        "Spend (list price)": _fmt_money(extra.get("spend")),
    }
    cli_versions = meta.get("cli_versions") or meta.get("providers") or {}
    if isinstance(cli_versions, dict) and cli_versions:
        rows["CLI versions"] = ", ".join(f"{k}: {v}" for k, v in cli_versions.items())
    items = "".join(f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in rows.items())
    return f'<dl class="meta-grid">{items}</dl>'


def _render_dispatch_report(run_dir: Path, meta: dict[str, Any]) -> str:
    summary_path = run_dir / "summary.json"
    if summary_path.is_file():
        summary = _load_json(summary_path)
    else:
        from model_routing.dispatch.report import summarize

        summary = summarize(run_dir)

    banner = (
        '<div class="banner">SIMULATED &mdash; no real models were called</div>'
        if summary.get("fake")
        else ""
    )
    headline = f'<div class="headline">{_esc(summary.get("headline", ""))}</div>'

    policy_rows = "".join(
        f"<tr><td>{_esc(p['name'])}</td><td class='num'>{p['n']}</td>"
        f"<td class='num'>{_fmt_pct(p.get('pass_rate'))}</td>"
        f"<td class='num'>{_fmt_money(p.get('cost_per_task'))}</td>"
        f"<td class='num'>{_fmt_money(p.get('cost_per_pass'))}</td>"
        f"<td class='num'>{_fmt_pct(p.get('router_share'))}</td>"
        f"<td class='num'>{_fmt_pct(p.get('escalation_rate'))}</td></tr>"
        for p in summary.get("policies", [])
    )
    oracle = summary.get("oracle")
    if oracle:
        policy_rows += (
            f"<tr><td>oracle (computed)</td><td class='num'>{oracle['n']}</td>"
            f"<td class='num'>{_fmt_pct(oracle.get('pass_rate'))}</td>"
            f"<td class='num'>{_fmt_money(oracle.get('cost_per_task'))}</td>"
            f"<td class='num'>{_fmt_money(oracle.get('cost_per_pass'))}</td>"
            "<td class='num'>-</td><td class='num'>-</td></tr>"
        )
    comparisons = "".join(
        f"<tr><td>{_esc(c['id'])}</td><td>{_esc(c['treatment'])}</td><td>{_esc(c['control'])}</td>"
        f"<td class='verdict-{_esc(c['verdict']).replace(' ', '_')}'>{_esc(c['verdict'])}</td>"
        f"<td>{_esc(c['sentence'])}</td></tr>"
        for c in summary.get("comparisons", [])
    )

    return f"""
{banner}
{headline}
<h2>Run metadata</h2>
{_meta_table(meta, {"spend": summary.get("spent_usd")})}
<h2>Policies</h2>
<table><thead><tr><th>Policy</th><th class="num">n</th><th class="num">Pass rate</th>
<th class="num">Cost/task</th><th class="num">Cost/completed task</th>
<th class="num">Router share</th><th class="num">Escalation rate</th></tr></thead>
<tbody>{policy_rows}</tbody></table>
<h2>Comparisons</h2>
<table><thead><tr><th>id</th><th>treatment</th><th>control</th><th>verdict</th>
<th>sentence</th></tr></thead><tbody>{comparisons}</tbody></table>
<h2>Power</h2>
<p class="small">{_esc(summary.get("power_note", ""))}</p>
"""


def _render_single_shot_report(run_dir: Path, meta: dict[str, Any]) -> str:
    # Note: this never writes to ``run_dir`` (no ``write_report`` call) -- it
    # is called from ``backup_run``, and a report render must not mutate the
    # source directory it is about to hash and copy.
    from model_routing.report import aggregate, load_outcomes, render_markdown

    spend = None
    table = ""
    outcomes: list[dict[str, Any]] = []
    try:
        outcomes = load_outcomes(run_dir)
        stats = aggregate(outcomes)
        spend = sum(s.cost for s in stats)
        rows = "".join(
            f"<tr><td>{_esc(s.router)}</td><td class='num'>{s.n}</td>"
            f"<td class='num'>{_fmt_pct(s.pass_rate)}</td>"
            f"<td class='num'>{_fmt_money(s.cost_per_task)}</td>"
            f"<td class='num'>{_fmt_money(s.cost_per_pass)}</td>"
            f"<td class='num'>{s.escalations}</td></tr>"
            for s in stats
        )
        table = (
            "<h2>Routers</h2><table><thead><tr><th>Router</th><th class='num'>n</th>"
            "<th class='num'>Pass rate</th><th class='num'>Cost/task</th>"
            "<th class='num'>Cost/completed task</th><th class='num'>Escalations</th></tr>"
            f"</thead><tbody>{rows}</tbody></table>"
        )
    except (OSError, ValueError, KeyError):
        pass

    summary_md = run_dir / "summary.md"
    if summary_md.is_file():
        md_text = summary_md.read_text()
    elif outcomes:
        md_text = render_markdown(run_dir, outcomes)
    else:
        md_text = "No summary.md for this run."
    banner = (
        '<div class="banner">SIMULATED &mdash; no real models were called</div>'
        if is_fake_run(run_dir)
        else ""
    )
    return f"""
{banner}
<h2>Run metadata</h2>
{_meta_table(meta, {"spend": spend})}
{table}
<h2>summary.md</h2>
<pre>{_esc(md_text)}</pre>
"""


def render_report_html(run_dir: str | Path) -> str:
    """A standalone, self-contained, printable HTML report for one run."""
    run_dir = Path(run_dir)
    meta = _load_json(run_dir / "meta.json")
    experiment, stamp = run_identity(run_dir)
    title = f"{experiment} / {stamp}"
    if is_dispatch_run(run_dir):
        body = _render_dispatch_report(run_dir, meta)
    else:
        body = _render_single_shot_report(run_dir, meta)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} — model-routing report</title>
<style>{_REPORT_CSS}</style>
</head>
<body>
<h1>{_esc(title)}</h1>
<p class="muted small">Rendered {_esc(datetime.now(UTC).isoformat())} by
model-routing {_esc(__version__)}. This is a standalone snapshot; regenerate it from the run
directory for the latest data.</p>
{body}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Export (zip)
# ---------------------------------------------------------------------------

_README_TEMPLATE = """model-routing run export
=========================

Run: {experiment}/{stamp}
Exported: {exported_at}

What's in this zip
-------------------
- Every file from the run directory (JSONL call/outcome logs, meta.json,
  config.toml, summary.md/csv/json) except any ``sandboxes/`` directory
  (throwaway per-task working copies used by dispatch runs, not data).
- report.html: a standalone, printable snapshot of this run's report. Open it
  in any browser; no server or dependency is required.

Source of truth
----------------
The JSONL files (outcomes.jsonl / calls.jsonl, or sessions.jsonl for a
dispatch run) are the source of truth for this run. meta.json records the
config, task manifest, and hashes used to reproduce it. summary.md/json are
derived and can be regenerated from the JSONL with:

    model-routing report results/{experiment}/{stamp}          # single-shot
    model-routing dispatch-report results/{experiment}/{stamp}  # dispatch

How to restore
---------------
1. Unzip this archive.
2. Copy the unzipped folder (everything except report.html and this README)
   to ``results/{experiment}/{stamp}/`` in a model-routing checkout.
3. Run ``model-routing dashboard`` (or ``model-routing report``/
   ``dispatch-report`` on the directory) to rebuild the SQLite index and
   summary files.

Or use the harness directly: ``model-routing restore <this-folder's-parent>``
if it was produced by ``model-routing backup`` (that command additionally
writes a manifest.json per run with sha256 hashes for verification).
"""


def export_run(run_dir: str | Path, out_dir: str | Path | None = None) -> Path:
    """Zip every file in ``run_dir`` (except ``sandboxes/``), plus a report and README."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise ValueError(f"Not a run directory: {run_dir}")
    experiment, stamp = run_identity(run_dir)
    out_dir = Path(out_dir) if out_dir else run_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{export_basename(run_dir)}.zip"
    zip_path = out_dir / zip_name

    report_html = render_report_html(run_dir)
    readme = _README_TEMPLATE.format(
        experiment=experiment, stamp=stamp, exported_at=datetime.now(UTC).isoformat()
    )

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(run_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(run_dir)
            if rel.parts and rel.parts[0] == "sandboxes":
                continue
            zf.write(path, arcname=str(Path(experiment) / stamp / rel))
        zf.writestr(str(Path(experiment) / stamp / "report.html"), report_html)
        zf.writestr(str(Path(experiment) / stamp / "README.txt"), readme)
    return zip_path


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_files(run_dir: Path) -> list[Path]:
    out = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir)
        if rel.parts and rel.parts[0] == "sandboxes":
            continue
        out.append(path)
    return out


def backup_run(run_dir: str | Path, settings: Settings | None = None) -> dict[str, Any]:
    """Copy one run's files, report, and a zip into the backup directory.

    Idempotent: files already present with a matching hash are skipped.
    Never deletes anything already in the backup directory.
    """
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise ValueError(f"Not a run directory: {run_dir}")
    settings = settings or Settings.load()
    if settings.backup_dir is None:
        raise ValueError("No backup directory configured")
    experiment, stamp = run_identity(run_dir)
    dest = Path(settings.backup_dir) / experiment / stamp
    dest.mkdir(parents=True, exist_ok=True)

    # Render the report (and, for a dispatch run missing summary.json, let it
    # regenerate that derived file) *before* snapshotting which files the run
    # directory has, so a first-time regeneration is captured by this same
    # backup pass rather than looking like drift on the next one.
    report_html = render_report_html(run_dir)

    copied: list[str] = []
    skipped: list[str] = []
    for src in _run_files(run_dir):
        rel = src.relative_to(run_dir)
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.is_file() and _sha256(dst) == _sha256(src):
            skipped.append(str(rel))
            continue
        shutil.copy2(src, dst)
        if _sha256(dst) != _sha256(src):
            raise OSError(f"Backup verification failed for {rel}")
        copied.append(str(rel))

    (dest / "report.html").write_text(report_html)

    # A flat, chronologically sorted folder of human-facing exports, so the
    # backup can be browsed in Drive without opening per-run folders.
    reports_dir = Path(settings.backup_dir) / REPORTS_DIRNAME
    reports_dir.mkdir(parents=True, exist_ok=True)
    zip_path = export_run(run_dir, out_dir=reports_dir)
    report_path = reports_dir / f"{export_basename(run_dir)}_report.html"
    report_path.write_text(report_html)

    manifest = {
        "experiment": experiment,
        "stamp": stamp,
        "backed_up_at": datetime.now(UTC).isoformat(),
        "source_dir": str(run_dir),
        "files": {
            str(p.relative_to(dest)): _sha256(p)
            for p in sorted(dest.rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))

    return {
        "run_id": f"{experiment}/{stamp}",
        "dest": str(dest),
        "copied": copied,
        "skipped": skipped,
        "zip": str(zip_path),
        "report": str(report_path),
        "status": "up-to-date" if not copied else "backed-up",
    }


def _snapshot_index(results_dir: Path, settings: Settings) -> str | None:
    db_path = results_dir / "index.sqlite"
    if not db_path.is_file() or settings.backup_dir is None:
        return None
    index_dir = Path(settings.backup_dir) / "_index"
    index_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = index_dir / f"index-{stamp}.sqlite"
    src_conn = sqlite3.connect(db_path)
    dst_conn = sqlite3.connect(dest)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    snapshots = sorted(index_dir.glob("index-*.sqlite"))
    for stale in snapshots[:-KEEP_INDEX_SNAPSHOTS]:
        stale.unlink(missing_ok=True)
    return str(dest)


def _backup_dispatch_jobs(results_dir: Path, settings: Settings) -> int:
    jobs_dir = results_dir / "dispatch_jobs"
    if not jobs_dir.is_dir() or settings.backup_dir is None:
        return 0
    dest_dir = Path(settings.backup_dir) / "_dispatch_jobs"
    dest_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for src in jobs_dir.glob("*.json"):
        dst = dest_dir / src.name
        if dst.is_file() and _sha256(dst) == _sha256(src):
            continue
        shutil.copy2(src, dst)
        n += 1
    return n


def latest_index_snapshot(settings: Settings | None = None) -> str | None:
    settings = settings or Settings.load()
    if settings.backup_dir is None:
        return None
    index_dir = Path(settings.backup_dir) / "_index"
    if not index_dir.is_dir():
        return None
    snapshots = sorted(index_dir.glob("index-*.sqlite"))
    return str(snapshots[-1]) if snapshots else None


def backup_all(results_dir: str | Path, settings: Settings | None = None) -> dict[str, Any]:
    results_dir = Path(results_dir)
    settings = settings or Settings.load()
    if settings.backup_dir is None:
        raise ValueError("No backup directory configured")
    runs = []
    for run_dir in discover_all_runs(results_dir):
        try:
            runs.append(backup_run(run_dir, settings))
        except Exception as exc:  # keep going; report the failure, don't lose others
            runs.append({"run_id": str(run_dir), "status": "failed", "error": str(exc)})
    index_snapshot = _snapshot_index(results_dir, settings)
    jobs_copied = _backup_dispatch_jobs(results_dir, settings)
    return {
        "runs": runs,
        "index_snapshot": index_snapshot,
        "dispatch_jobs_copied": jobs_copied,
    }


def backup_status(
    results_dir: str | Path, settings: Settings | None = None
) -> list[dict[str, Any]]:
    results_dir = Path(results_dir)
    settings = settings or Settings.load()
    out = []
    for run_dir in discover_all_runs(results_dir):
        experiment, stamp = run_identity(run_dir)
        entry: dict[str, Any] = {
            "run_id": f"{experiment}/{stamp}",
            "run_dir": str(run_dir.relative_to(results_dir)),
            "fake": is_fake_run(run_dir),
            "backed_up": False,
            "up_to_date": False,
            "backed_up_at": None,
        }
        if settings.backup_dir is not None:
            dest = Path(settings.backup_dir) / experiment / stamp
            manifest_path = dest / "manifest.json"
            if manifest_path.is_file():
                manifest = _load_json(manifest_path)
                entry["backed_up"] = True
                entry["backed_up_at"] = manifest.get("backed_up_at")
                up_to_date = True
                for src in _run_files(run_dir):
                    rel = str(src.relative_to(run_dir))
                    expected = manifest.get("files", {}).get(rel)
                    if expected is None or expected != _sha256(src):
                        up_to_date = False
                        break
                entry["up_to_date"] = up_to_date
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def restore(backup_dir: str | Path, results_dir: str | Path) -> dict[str, Any]:
    """Copy runs missing from ``results_dir`` back in, verify manifests, reindex.

    Never overwrites a local file that differs from the backup; such runs are
    reported as conflicts instead, and left untouched locally.
    """
    backup_dir = Path(backup_dir)
    results_dir = Path(results_dir)
    if not backup_dir.is_dir():
        raise ValueError(f"Not a backup directory: {backup_dir}")
    restored: list[str] = []
    conflicts: list[dict[str, Any]] = []
    verified_bad: list[str] = []

    for manifest_path in sorted(backup_dir.glob("*/*/manifest.json")):
        run_backup_dir = manifest_path.parent
        manifest = _load_json(manifest_path)
        experiment = manifest.get("experiment") or run_backup_dir.parent.name
        stamp = manifest.get("stamp") or run_backup_dir.name
        run_id = f"{experiment}/{stamp}"
        local_dir = results_dir / experiment / stamp

        # Verify the backup copy itself before trusting it.
        bad_files = [
            rel
            for rel, expected in manifest.get("files", {}).items()
            if (run_backup_dir / rel).is_file() and _sha256(run_backup_dir / rel) != expected
        ]
        if bad_files:
            verified_bad.append(run_id)
            continue

        if not local_dir.is_dir():
            local_dir.mkdir(parents=True, exist_ok=True)
            for rel in manifest.get("files", {}):
                if rel in ("manifest.json", "report.html") or rel.endswith(".zip"):
                    continue
                src = run_backup_dir / rel
                if not src.is_file():
                    continue
                dst = local_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            restored.append(run_id)
            continue

        # Local copy exists: only fill in files that are missing; never
        # overwrite ones that differ.
        run_conflicts = []
        for rel in manifest.get("files", {}):
            if rel in ("manifest.json", "report.html") or rel.endswith(".zip"):
                continue
            src = run_backup_dir / rel
            if not src.is_file():
                continue
            dst = local_dir / rel
            if not dst.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            elif _sha256(dst) != _sha256(src):
                run_conflicts.append(rel)
        if run_conflicts:
            conflicts.append({"run_id": run_id, "files": run_conflicts})

    from model_routing.store import index_results

    indexed = index_results(results_dir, results_dir / "index.sqlite")
    return {
        "restored": restored,
        "conflicts": conflicts,
        "corrupt_backups": verified_bad,
        "indexed": indexed,
    }


# ---------------------------------------------------------------------------
# Automatic backup hook
# ---------------------------------------------------------------------------


def auto_backup(run_dir: str | Path, *, log: Any = None) -> dict[str, Any] | None:
    """Back up ``run_dir`` if auto-backup is on and the run is real.

    Failures are logged (loudly, if ``log`` is given) but never raised: a
    backup problem must not crash or corrupt the run that triggered it.
    """
    run_dir = Path(run_dir)
    log = log or (lambda msg: print(msg, flush=True))  # noqa: T201
    try:
        if is_fake_run(run_dir):
            return None
        settings = Settings.load()
        if not settings.auto_backup or settings.backup_dir is None:
            return None
        result = backup_run(run_dir, settings)
        log(f"backup: {result['run_id']} -> {result['dest']} ({result['status']})")
        return result
    except Exception as exc:  # never let a backup failure take down a run
        log(f"backup FAILED for {run_dir}: {exc}")
        return None
