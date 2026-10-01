"""Static JSON export for the cost dashboard.

``export`` writes ``index.json``, ``pipelines/<slug>.json``,
``runs/page-<k>.json`` and ``inflight.json`` under an output directory, all as
``json.dumps(obj, indent=2, sort_keys=True)`` plus a newline. It reads and
computes everything first and only then writes, so a failure leaves the
directory as it was. ``.export-manifest.json`` lists what the export wrote;
the next export deletes files from that list it no longer writes, and never
touches anything else.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from orchestra.dag import DAG
from orchestra.model import JobSpec
from toolbelt.text import unique_slugs

from ledger import store

MANIFEST = ".export-manifest.json"


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _iso(record: store.RunRecord) -> str:
    return record.to_dict()["started_at"]


def export(
    out_dir: str | Path,
    history: str | Path,
    inflight: str | Path | None = None,
    specs_dir: str | Path | None = None,
    page_size: int = 50,
) -> list[str]:
    out = Path(out_dir)
    records = store.load(history)
    running: list[tuple[str, dict[str, Any]]] = []
    if inflight is not None and Path(inflight).exists():
        entries = json.loads(Path(inflight).read_text())
        running = [(rid, e) for rid, e in entries.items() if e["status"] == "running"]
    slugs = unique_slugs(sorted({r.pipeline for r in records} | {e["pipeline"] for _, e in running}))

    def summary(r: store.RunRecord) -> dict[str, Any]:
        return {"run_id": r.run_id, "pipeline": r.pipeline, "slug": slugs[r.pipeline],
                "started_at": _iso(r), "status": r.status, "total_usd": round(r.total_usd, 2)}

    files: dict[str, Any] = {}
    ordered = sorted(sorted(records, key=lambda r: r.run_id), key=lambda r: r.started_at, reverse=True)
    pages = max(1, math.ceil(len(ordered) / page_size))
    for k in range(1, pages + 1):
        chunk = ordered[(k - 1) * page_size : k * page_size]
        files[f"runs/page-{k}.json"] = {"page": k, "pages": pages, "page_size": page_size, "runs": [summary(r) for r in chunk]}
    for name, slug in slugs.items():
        mine = [r for r in records if r.pipeline == name]
        months: dict[str, dict[str, Any]] = {}
        for r in mine:
            m = months.setdefault(r.month, {"runs": 0, "total_usd": 0.0})
            m["runs"] += 1
            m["total_usd"] += r.total_usd
        for m in months.values():
            m["total_usd"] = round(m["total_usd"], 2)
        last = max(mine, key=lambda r: (r.started_at, r.run_id), default=None)
        jobs = path = seconds = None
        spec_file = Path(specs_dir) / f"{slug}.json" if specs_dir is not None else None
        if spec_file is not None and spec_file.exists():
            specs = [JobSpec.from_dict(d) for d in json.loads(spec_file.read_text())]
            jobs = len(specs)
            path, seconds = DAG(specs).critical_path()
        files[f"pipelines/{slug}.json"] = {
            "pipeline": name, "slug": slug, "runs": len(mine), "total_usd": round(sum(r.total_usd for r in mine), 2),
            "months": months, "last_run": summary(last) if last else None,
            "jobs": jobs, "critical_path": path, "critical_path_seconds": seconds,
        }
    live = sorted(running, key=lambda item: (item[1]["started_at"], item[0]))
    files["inflight.json"] = {"count": len(live), "running": [
        {"run_id": rid, "pipeline": e["pipeline"], "slug": slugs[e["pipeline"]], "started_at": e["started_at"]} for rid, e in live
    ]}
    files["index.json"] = {
        "schema_version": 1,
        "generated_from": {"history_records": len(records), "inflight_running": len(live)},
        "pipelines": dict(sorted(slugs.items())),
        "months": sorted({r.month for r in records}, reverse=True),
        "run_pages": pages,
    }
    rendered = {rel: _dump(obj) for rel, obj in files.items()}

    # --- write phase: nothing above touches out_dir ---
    previous: list[str] = []
    manifest = out / MANIFEST
    if manifest.exists():
        previous = json.loads(manifest.read_text())
    out.mkdir(parents=True, exist_ok=True)
    for rel, text in rendered.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    written = sorted(rendered)
    for rel in previous:
        if rel not in rendered:
            stale = out / rel
            stale.unlink(missing_ok=True)
            parent = stale.parent
            while parent != out and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    manifest.write_text(json.dumps(written, indent=2) + "\n")
    return written
