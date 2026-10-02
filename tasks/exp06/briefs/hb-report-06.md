---
title: Finance-ready monthly report
terse: Bucket ledger history by month in a chosen time zone, add nearest-rank percentiles, and render the report as text, CSV and Markdown with rows that add up.
repo: platform
parent: platform
allowed: ["packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [long-horizon, reporting, time-zones, formats]
stratum: B
max_turns: 80
harvest_shape: "operator-facing output change with exact formats, measured problem and do-not-overstate constraints (harvested #14/#21 style)"
authorship: "Brief drafted from the shape of harvested dispatches by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Finance wants the ledger's monthly report in a form they can file, and the current one has a correctness problem as well as a format one. You are in the `platform` monorepo (current directory); `python -m pytest -q` runs every suite.

## Problems (measured on September's history)

1. **Wrong month.** `ledger.store.query(month=...)` buckets runs by their UTC start. Finance closes books in `America/Chicago`. The nightly runs that start at 02:00 UTC on the 1st belong to the *previous* month in Chicago, so every month's report is off by one night at each end; September was off by $212.
2. **No distribution.** Finance asked for p50/p95/max per-run cost per pipeline: a single $900 nightly run is a different conversation from thirty $30 ones.
3. **Rows don't add up.** The text report rounds each row for display but computes the total from unrounded values, so the visible rows can differ from the visible total by a cent.
4. **Format.** They want CSV for the spreadsheet and Markdown for the monthly close doc.

## Required behaviour

1. **Time-zone months.** `RunRecord.month_in(tz: str) -> str` returns `YYYY-MM` of `started_at` converted to the IANA zone `tz` (`zoneinfo`). `store.query` gains `tz: str = "UTC"`, used when `month` is given. Existing calls without `tz` behave exactly as today.
2. **Rows.** `report.monthly_rows(records, month, tz="UTC") -> list[Row]`, where `Row` is a frozen dataclass `pipeline, runs, total_usd, p50_usd, p95_usd, max_usd`. Percentiles use the **nearest-rank** method over that pipeline's per-run `total_usd` values: sort ascending; the P-th percentile is the value at 1-based rank `ceil(P / 100 * n)`. Rows are ordered by `total_usd` descending, then pipeline name.
3. **Display rounding.** Every amount shown is the value rounded half-even to cents, computed as `Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_EVEN)`. The total shown on a total line is the **sum of the displayed row totals**, so the visible rows always add up to the visible total.
4. **Renderers** in `ledger.report`:
   - `render_text(rows, month) -> str` — exactly today's `monthly_report` layout (header, blank line, `f"{pipeline:<24} {runs:>4} runs  ${total:>10.2f}"` rows, blank line, total line) with the rounding rule above. `monthly_report(records, month)` stays and equals `render_text(monthly_rows(records, month), month)`.
   - `render_csv(rows) -> str` — via the `csv` module with `\n` line endings: header `pipeline,runs,total_usd,p50_usd,p95_usd,max_usd`, one line per row with amounts as plain two-decimal numbers (`1234.50`, no `$`, no thousands separator), then `TOTAL,<runs>,<total>,,,`.
   - `render_markdown(rows, month, tz) -> str` — exactly:
     ```
     ## Spend for 2026-09 (America/Chicago)

     | pipeline | runs | total | p50 | p95 | max |
     |---|---:|---:|---:|---:|---:|
     | nightly | 30 | $1,234.50 | $40.00 | $55.10 | $61.00 |
     | **total** | 31 | **$1,300.00** | | | |
     ```
     Amounts use `$` with thousands separators. A `|` in a pipeline name is escaped as `\|`. The text ends with a single newline.
   - With no runs in the month: text keeps its header and a zero total line, CSV is the header plus `TOTAL,0,0.00,,,`, Markdown the heading, table header and a total row of 0 runs and `**$0.00**`.
5. **CLI.** `ledger report --month M [--tz TZ] [--format text|csv|markdown]` (defaults `UTC`, `text`). An unknown zone exits with status 2 and prints `unknown time zone: <TZ>` to stderr.

## Constraints

- Stdlib only. Keep every existing public name; update the `ledger.store` and `ledger.report` docstrings and the ledger README.
- Add tests in `packages/ledger/tests/`, including a run on the 1st at 02:00 UTC that lands in the previous month in Chicago, and a rounding case where naive per-row rounding would not add up.
- Report back: the files you changed, the percentile definition you implemented, and any existing caller you had to adjust.
