"""Monthly spend report (plain text)."""

from __future__ import annotations

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
