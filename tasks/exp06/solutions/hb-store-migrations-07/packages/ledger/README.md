# ledger

Cost and run history for orchestra pipelines.

| module | role |
|---|---|
| `ledger.rates` | the rate card (USD per unit-second per resource pool) |
| `ledger.pricing` | pricing a finished run, attempt by attempt |
| `ledger.store` | the run history (`history.jsonl`), upgraded on read through `ledger.migrations` |
| `ledger.migrations` | declarative history migrations and the chain check (`docs/ledger-migrations.md`) |
| `ledger.budget` | monthly budgets and over-budget alerts |
| `ledger.report` | the monthly spend report |
| `ledger.inflight` | runs still in flight, and reaping dead ones |
| `ledger.cli` | the `ledger` command |

Depends on `orchestra` (run results and job specs) and `toolbelt`.
