# ledger

Cost and run history for orchestra pipelines.

| module | role |
|---|---|
| `ledger.rates` | the rate card (USD per unit-second per resource pool) |
| `ledger.pricing` | pricing a finished run, attempt by attempt |
| `ledger.store` | the run history (`history.jsonl`) |
| `ledger.budget` | per-pipeline budget policy (null inherits the default), alerts and run admission |
| `ledger.report` | the monthly spend report |
| `ledger.inflight` | runs still in flight, and reaping dead ones |
| `ledger.cli` | the `ledger` command |

Depends on `orchestra` (run results and job specs) and `toolbelt`.
