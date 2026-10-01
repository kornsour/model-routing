# platform

The data platform monorepo.

| package | what it is |
|---|---|
| `packages/orchestra` | deterministic job-DAG scheduler (simulation and planning core of the runner) |
| `packages/toolbelt` | stdlib-only helpers shared by every service (money, durations, ini config, text) |
| `packages/ledger` | cost and run history for orchestra pipelines |

Every package is stdlib-only and uses a `src/` layout. The root `conftest.py`
puts each `packages/*/src` on the path, so one `python -m pytest -q` at the
root runs all three suites with nothing installed.

Conventions: each package documents its own contract (module docstrings and
`docs/`); a change to a documented behaviour updates the doc in the same
change; no package imports another package's private names (leading `_`).
