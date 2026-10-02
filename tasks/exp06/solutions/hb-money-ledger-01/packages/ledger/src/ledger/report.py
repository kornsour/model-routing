"""Monthly spend report (plain text). Amounts are summed in minor units, so
the rows always add up to the total line."""

from __future__ import annotations

from toolbelt.money import format_money

from ledger.store import RunRecord, query


def monthly_report(records: list[RunRecord], month: str) -> str:
    rows: dict[str, tuple[int, int]] = {}
    for r in query(records, month=month):
        n, total = rows.get(r.pipeline, (0, 0))
        rows[r.pipeline] = (n + 1, total + r.total_minor)
    lines = [f"Spend for {month}", ""]
    for pipeline, (n, total) in sorted(rows.items(), key=lambda kv: (-kv[1][1], kv[0])):
        lines.append(f"{pipeline:<24} {n:>4} runs  {format_money(total, 'USD'):>12}")
    grand = sum(t for _, t in rows.values())
    count = sum(n for n, _ in rows.values())
    lines += ["", f"{'total':<24} {count:>4} runs  {format_money(grand, 'USD'):>12}"]
    return "\n".join(lines) + "\n"
