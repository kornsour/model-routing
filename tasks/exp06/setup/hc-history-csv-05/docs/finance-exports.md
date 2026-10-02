# Finance exports

Finance loads every export we hand them into the same spreadsheet model, so
all of them follow one set of conventions. Agreed with finance in July 2026.

1. CSV, comma-separated, a header row, `\n` line endings, minimal quoting.
2. Column names are `snake_case`; money columns end in `_usd`.
3. Money: US dollars with exactly two decimals, rounded half-even
   (`12.50`, never `12.5` or `$12.50`).
4. Timestamps: UTC, ISO 8601, seconds precision, with a `Z` suffix
   (`2026-09-01T02:00:00Z`). Months are UTC calendar months.
5. Rows in chronological order; ties broken by the record's id.
6. One row per record; no total rows (finance computes totals).

## Exports and their columns

| export | columns |
|---|---|
| monthly spend by pipeline | `month, pipeline, runs, total_usd` |
| run history | `run_id, pipeline, started_at, status, total_usd` |
| budget alerts | `month, pipeline, spent_usd, budget_usd` |
