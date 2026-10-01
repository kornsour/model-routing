# ledger

Cost and run history for orchestra pipelines.

| module | role |
|---|---|
| `ledger.rates` | the rate card (exact `Decimal` USD per unit-second per resource pool) |
| `ledger.pricing` | pricing a finished run, attempt by attempt |
| `ledger.store` | the run history (`history.jsonl`, format 2: integer minor units; reads format 1) |
| `ledger.budget` | monthly budgets and over-budget alerts |
| `ledger.report` | the monthly spend report |
| `ledger.inflight` | runs still in flight, and reaping dead ones |
| `ledger.cli` | the `ledger` command |

Depends on `orchestra` (run results and job specs) and `toolbelt`.

Money is exact: rates and attempt costs are `Decimal`, stored and displayed
amounts are integer minor units, and every split of a total uses
`toolbelt.money.allocate`, so parts always add up to their total.
