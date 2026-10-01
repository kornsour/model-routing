# Budgets runbook

`budgets.json` sets each pipeline's monthly budget (see the `ledger.budget`
docstring for the format). `ledger budgets --month M` runs after every
nightly run from cron; its exit status pages the on-call engineer, so a
non-zero exit must mean "something is actually over budget".

## Alerts

A pipeline whose month-to-date spend is strictly over its budget gets a line

    OVER nightly: $201.50 of $200.00

and the command exits 1.

## Early warnings (requested, not built yet)

Finance wants a heads-up before a pipeline goes over, at the same threshold
the cloud billing alerts use: **80% of the budget**. Some orgs tune it, so it
should be overridable with a top-level `warn_fraction` in `budgets.json`.
Warnings are informational: they appear in the same output, in the same
format as an alert line with `WARN` in place of `OVER`, and they must never
page anyone on their own.
