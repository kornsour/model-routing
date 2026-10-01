---
title: Run history as CSV for finance
terse: Add a ledger command that exports a month of run history as CSV for finance.
repo: platform
parent: platform
allowed: ["packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [ambiguous, export, csv]
stratum: C
max_turns: 40
missing_requirement: "Columns, money and timestamp formats, ordering and totals are not stated; docs/finance-exports.md defines all of them for every finance export, including the run-history columns."
answer_key: {"question": "Which columns and formats should the CSV use?", "answer": "Follow docs/finance-exports.md: header run_id,pipeline,started_at,status,total_usd; started_at in UTC with a Z suffix and seconds precision; total_usd with two decimals rounded half-even; rows in started_at order with ties by run_id; no total row; UTC months."}
harvest_shape: "short export request from a stakeholder with no format spec (harvested chip style)"
authorship: "Brief drafted from the shape of harvested chips by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Finance asked for the raw run history behind each month's report so they can reconcile it against the cloud invoice line by line. Please add `ledger history-csv --month YYYY-MM [--history F]`, printing that month's runs as CSV on stdout, one row per run. Put the logic in `ledger.report` (a `history_csv(records, month) -> str` function) so the dashboard can reuse it. Add tests and keep `python -m pytest -q` green.
