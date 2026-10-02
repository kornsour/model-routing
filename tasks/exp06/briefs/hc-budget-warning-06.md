---
title: Early budget warnings
terse: Warn in `ledger budgets` before a pipeline goes over its monthly budget.
repo: platform
parent: platform
allowed: ["packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [ambiguous, budgets, cli]
stratum: C
max_turns: 40
missing_requirement: "The threshold, the output format and the exit-status behaviour of warnings are not stated; docs/budgets.md specifies 80% (overridable via warn_fraction), the OVER-line format with WARN, and that warnings never change the exit status."
answer_key: {"question": "When should a warning fire, what should it print, and should it change the exit status?", "answer": "Per docs/budgets.md: warn when month-to-date spend is at least warn_fraction (default 0.8, top-level in budgets.json) of the budget but not over it; print it in the alert line's format with WARN instead of OVER; warnings alone exit 0, and the exit status stays 1 only when something is over."}
harvest_shape: "feature chip from a stakeholder message; the specifics live in a runbook the brief does not cite (harvested chip style)"
authorship: "Brief drafted from the shape of harvested chips by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Finance's ask from Monday's review: "We only hear about a pipeline once it's already over budget. Can the nightly budget check give us early warning?"

Please add early warnings to `ledger budgets` (in `ledger.budget` and the CLI), with tests, and keep `python -m pytest -q` green.
