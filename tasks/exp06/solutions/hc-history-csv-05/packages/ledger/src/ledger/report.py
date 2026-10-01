"""Monthly spend report (plain text) and the finance run-history CSV.

``history_csv`` follows ``docs/finance-exports.md``: columns ``run_id,
pipeline, started_at, status, total_usd``; UTC ``Z`` timestamps; dollars with
two decimals rounded half-even; chronological order, ties by run id.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC
from decimal import ROUND_HALF_EVEN, Decimal

from ledger.store import RunRecord, query


def monthly_report(records: list[RunRecord], month: str) -> str:
    rows: dict[str, tuple[int, float]] = {}
    for r in query(records, month=month):
        n, total = rows.get(r.pipeline, (0, 0.0))
        rows[r.pipeline] = (n + 1, total + r.total_usd)
    lines = [f"Spend for {month}", ""]
    for pipeline, (n, total) in sorted(rows.items(), key=lambda kv: (-kv[1][1], kv[0])):
        lines.append(f"{pipeline:<24} {n:>4} runs  ${total:>10.2f}")
    grand = sum(t for _, t in rows.values())
    lines += ["", f"{'total':<24} {sum(n for n, _ in rows.values()):>4} runs  ${grand:>10.2f}"]
    return "\n".join(lines) + "\n"


def history_csv(records: list[RunRecord], month: str) -> str:
    buf = io.StringIO()
    out = csv.writer(buf, lineterminator="\n")
    out.writerow(["run_id", "pipeline", "started_at", "status", "total_usd"])
    in_month = [r for r in records if r.started_at.astimezone(UTC).strftime("%Y-%m") == month]
    for rec in sorted(in_month, key=lambda x: (x.started_at, x.run_id)):
        stamp = rec.started_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        usd = Decimal(str(rec.total_usd)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        out.writerow([rec.run_id, rec.pipeline, stamp, rec.status, f"{usd:.2f}"])
    return buf.getvalue()
