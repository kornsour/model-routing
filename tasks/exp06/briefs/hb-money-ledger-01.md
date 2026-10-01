---
title: Make ledger money exact, end to end
terse: Replace ledger's float USD with exact Decimal rates and integer minor units everywhere, with a backward-compatible history format.
repo: platform
parent: platform
allowed: ["packages/ledger/*", "packages/toolbelt/*", "docs/*", "README.md"]
category: refactor
tags: [long-horizon, multi-package, money, data-format]
stratum: B
max_turns: 80
harvest_shape: "cross-cutting type change with a migration path (harvested #29: EndedAt to *time.Time across store, API, client and docs)"
authorship: "Brief drafted from the shape of harvested cross-cutting dispatches by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Finance has started reconciling the ledger's monthly numbers against the cloud invoices, and they do not tie out. I need ledger's money handling made exact, end to end, in one coherent change. You are working in the `platform` monorepo (current directory); `python -m pytest -q` at the root runs every package's suite.

## What is wrong today (already investigated — build on this, don't re-derive it)

- `ledger.rates` parses the rate card to `float`, so `0.0004` is already `0.000400000000000000019…` before anything is multiplied.
- `ledger.pricing` computes every attempt's cost as a float, and `RunCost.total` / `by_job` are float sums.
- `ledger.store` writes `total_usd` and per-job `jobs` as JSON floats (format version 1). Every report and budget check reads those back.
- `ledger.report` formats each row with `:.2f` but computes the grand total from the unrounded floats, so in September the rows summed to $4,311.07 while the total line said $4,311.08. Finance noticed.
- `ledger.budget` compares float spend to a float budget; the `hourly` pipeline alerted at $500.0000000001 against a $500 budget.

`toolbelt.money` already has exact helpers (`to_minor`, `allocate`, `format_money`); ledger never adopted them. That is the fix: Decimal for rates and exact costs, integer minor units (cents) for every stored or displayed amount, and `allocate` wherever a total is split into parts so the parts always add up to the total.

## Required behaviour

1. **`toolbelt.money.from_minor(minor, currency) -> Decimal`** — new, the inverse of `to_minor`: `from_minor(1234, "USD") == Decimal("12.34")`, `from_minor(5, "JPY") == Decimal("5")`, `from_minor(-1, "KWD") == Decimal("-0.001")`. `minor` must be an `int` (a `bool` or `float` is a `TypeError`); an unknown currency is a `ValueError`, like the other helpers. Add it to the module's tests.
2. **Rates are `Decimal`.** `DEFAULT_RATES` and `load_rates` return `dict[str, Decimal]`. In `rates.json` a rate may be a JSON string (`"0.0004"`) or a JSON number; numbers must be read exactly (no float round trip). A negative rate, or anything that is not a finite number, is a `ValueError` naming the pool.
3. **Costs are exact.** `AttemptCost.cost`, `RunCost.by_job` values and `RunCost.total` are unrounded `Decimal`s. Attempt seconds come from the simulator's float times; convert each time with `Decimal(repr(t))` before subtracting, so `end - start` is exact for the times the simulator produces.
4. **`RunCost.minor(currency="USD") -> tuple[int, dict[str, int]]`** — the run total and per-job amounts in minor units. The total is `to_minor(total, currency)` (half-even). The per-job amounts are `allocate(total_minor, [exact job costs])` taken in sorted job-name order, so they always sum to the total; every job that had an attempt appears, and if every job cost is zero they are all `0`.
5. **History format version 2.** `RunRecord` now has `total_minor: int`, `jobs_minor: dict[str, int]` and `currency: str = "USD"` instead of `total_usd` / `jobs`. It keeps a read-only `total_usd` property returning `from_minor(total_minor, currency)`. A record whose `jobs_minor` is non-empty and does not sum to `total_minor` is a `ValueError` at construction. `to_dict` always writes:
   `{"version": 2, "run_id", "pipeline", "started_at", "status", "currency", "total_minor", "jobs_minor"}`.
   `from_dict` reads both versions; any other version is a `ValueError`. A version-1 record converts as: `total_minor = to_minor(Decimal(str(total_usd)), "USD")`, and `jobs_minor` re-allocates that total over `Decimal(str(v))` for each job in sorted job-name order (all zeros when every job is zero, `{}` when there are no jobs). History files in the wild mix version-1 and version-2 lines; `load` must handle any mix. Never rewrite existing lines.
6. **Budgets in minor units.** `budgets.json` amounts may be JSON numbers or strings and must be read exactly; an amount with more precision than cents (e.g. `500.005`) is a `ValueError`. `budget_for` and `month_to_date` return minor units (`int`); `Alert` becomes `Alert(pipeline, spent_minor, budget_minor)`. Alert only when spend is strictly greater than the budget.
7. **Report rows add up.** Each row's amount is the pipeline's summed `total_minor`, the grand total is the sum of the rows, and amounts render with `format_money(minor, "USD")` right-aligned in 12 characters, replacing the `$` + `:>10.2f` formatting. Everything else about the layout stays as it is today.
8. **CLI.** `ledger price` prints each job's allocated amount and the total with `format_money` (same `{job:<24} {amount}` line shape as today, `total` last); `ledger record` stores the version-2 record from `RunCost.minor()`; `ledger budgets` prints `format_money` amounts.

## Constraints

- Stdlib only; no package may import another package's private (`_`-prefixed) names. If ledger needs something from `toolbelt.money`, make it public.
- Keep every existing public name importable (`load_rates`, `price_run`, `RunRecord`, `append`, `load`, `query`, `check`, `budget_for`, `month_to_date`, `monthly_report`).
- Update the module docstrings that describe the formats (`ledger.rates`, `ledger.pricing`, `ledger.store`, `ledger.budget`) and the ledger README in the same change. Existing tests that assert float behaviour should be updated to the new contract, not deleted.
- `python -m pytest -q` at the root must be green.

## Report back

The files you changed and why, the exact version-1 conversion rule you implemented, and any place you found where a total was still being split without `allocate`.
