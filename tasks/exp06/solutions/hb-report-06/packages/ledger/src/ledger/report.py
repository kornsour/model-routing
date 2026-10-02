"""Monthly spend report: rows, then text, CSV or Markdown.

``monthly_rows`` groups a month's runs (in a chosen IANA time zone) by
pipeline with run count, total, and nearest-rank p50/p95 and max per-run cost:
sort ascending, the P-th percentile is the value at 1-based rank
``ceil(P / 100 * n)``. Every displayed amount is rounded half-even to cents,
and a total line shows the sum of the displayed row totals, so the visible
rows always add up.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from ledger.store import RunRecord, query

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Row:
    pipeline: str
    runs: int
    total_usd: float
    p50_usd: float
    p95_usd: float
    max_usd: float


def _percentile(sorted_values: list[float], p: int) -> float:
    rank = -(-p * len(sorted_values) // 100)
    return sorted_values[max(rank, 1) - 1]


def monthly_rows(records: list[RunRecord], month: str, tz: str = "UTC") -> list[Row]:
    per: dict[str, list[float]] = {}
    for r in query(records, month=month, tz=tz):
        per.setdefault(r.pipeline, []).append(r.total_usd)
    rows = []
    for pipeline, values in per.items():
        values = sorted(values)
        rows.append(Row(pipeline, len(values), sum(values), _percentile(values, 50), _percentile(values, 95), values[-1]))
    return sorted(rows, key=lambda r: (-r.total_usd, r.pipeline))


def _cents(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_EVEN)


def _grand(rows: list[Row]) -> Decimal:
    return sum((_cents(r.total_usd) for r in rows), Decimal("0.00"))


def render_text(rows: list[Row], month: str) -> str:
    lines = [f"Spend for {month}", ""]
    for r in rows:
        lines.append(f"{r.pipeline:<24} {r.runs:>4} runs  ${_cents(r.total_usd):>10.2f}")
    count = sum(r.runs for r in rows)
    lines += ["", f"{'total':<24} {count:>4} runs  ${_grand(rows):>10.2f}"]
    return "\n".join(lines) + "\n"


def monthly_report(records: list[RunRecord], month: str) -> str:
    return render_text(monthly_rows(records, month), month)


def render_csv(rows: list[Row]) -> str:
    buf = io.StringIO()
    out = csv.writer(buf, lineterminator="\n")
    out.writerow(["pipeline", "runs", "total_usd", "p50_usd", "p95_usd", "max_usd"])
    for r in rows:
        out.writerow([r.pipeline, r.runs, *(f"{_cents(v):.2f}" for v in (r.total_usd, r.p50_usd, r.p95_usd, r.max_usd))])
    out.writerow(["TOTAL", sum(r.runs for r in rows), f"{_grand(rows):.2f}", "", "", ""])
    return buf.getvalue()


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


def render_markdown(rows: list[Row], month: str, tz: str) -> str:
    lines = [
        f"## Spend for {month} ({tz})",
        "",
        "| pipeline | runs | total | p50 | p95 | max |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        name = r.pipeline.replace("|", "\\|")
        amounts = " | ".join(_money(_cents(v)) for v in (r.total_usd, r.p50_usd, r.p95_usd, r.max_usd))
        lines.append(f"| {name} | {r.runs} | {amounts} |")
    lines.append(f"| **total** | {sum(r.runs for r in rows)} | **{_money(_grand(rows))}** | | | |")
    return "\n".join(lines) + "\n"
