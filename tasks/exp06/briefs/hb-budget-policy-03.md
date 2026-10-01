---
title: Per-pipeline budget policy with inheritance and admission
terse: Turn ledger budgets into a per-pipeline policy where null means inherit, make the default's reach visible, and gate run admission on the policy.
repo: platform
parent: platform
allowed: ["packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [long-horizon, policy, inheritance, cli, data-format]
stratum: B
max_turns: 80
harvest_shape: "two issues extending one per-entity policy mechanism, with measured context and load-bearing design constraints (harvested #32: per-company policy, NULL means inherit)"
authorship: "Brief drafted from the shape of harvested dispatch #32 by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Two related requests against `ledger.budget` in the `platform` monorepo (current directory). They extend the same mechanism, so do them as one change: first make the policy explicit and inheritable, then use it to gate runs.

## Context (measured — do not re-measure)

`budgets.json` today is `{"default_monthly_usd": 500, "pipelines": {"nightly": 200, ...}}`. When the platform team raised the default to $500 last month, it changed nothing: 31 of the 33 pipelines carry their own number, most of them copied from the old default when the file was first written. Nobody can tell from the file which numbers were chosen and which were just copied, and there is no way to say "this pipeline follows the default" other than deleting its line by hand.

Separately, finance wants some pipelines **blocked** before they overspend rather than alerted after, while others should keep alerting, and a couple of exploratory pipelines should not be checked at all.

## Part 1 — an explicit, inheritable policy

1. New `budgets.json` format (version 2):
   ```json
   {"version": 2,
    "defaults": {"monthly_usd": 500, "enforce": "alert", "max_run_usd": null},
    "pipelines": {"nightly": {"monthly_usd": 200, "enforce": null, "max_run_usd": 40}}}
   ```
   Each pipeline field is optional; **a missing key or `null` means inherit the default**. `0` is a real value (a zero budget), never "inherit". `enforce` is one of `"alert"`, `"block"`, `"off"`; anything else is a `ValueError`. In `defaults`, `monthly_usd` is required; `enforce` defaults to `"alert"` and `max_run_usd` to `null` (no per-run cap).
2. `load_budgets(path)` reads both formats and returns the normalised version-2 dict. A version-1 file (no `version` key) converts as `defaults = {"monthly_usd": <default_monthly_usd>, "enforce": "alert", "max_run_usd": null}` and each `"pipeline": number` becomes `{"monthly_usd": number}`. `save_budgets(path, config)` always writes version 2 (sorted keys, 2-space indent).
3. `resolve(config, pipeline) -> Policy`, a frozen dataclass with `monthly_usd: float`, `enforce: str`, `max_run_usd: float | None` and `inherited: frozenset[str]` naming the fields that came from the defaults. A pipeline with no entry inherits everything. Keep `budget_for(config, pipeline)` returning the resolved monthly budget.
4. `reset_to_inherit(config, pipelines, field) -> int`: sets `field` to `null` for exactly the listed pipelines and returns how many changed. An unknown pipeline is a `KeyError`, an unknown field a `ValueError`. **Never clear overrides that were not listed** — those numbers may have been chosen deliberately; the operator decides, with the count in front of them.
5. `governed_by_default(config, pipelines, field="monthly_usd") -> list[str]`: the sorted subset of `pipelines` that inherit `field`.

## Part 2 — admission and checks follow the policy

6. `check(records, config, month)` skips pipelines whose resolved `enforce` is `"off"`; otherwise unchanged (alert when spend is strictly over budget). `Alert` gains an `enforce` field.
7. `admit(records, config, pipeline, month, estimate_usd) -> Decision` (a frozen dataclass `allowed: bool`, `reasons: tuple[str, ...]`) is what the scheduler calls before starting a run:
   - `"off"`: allowed, no reasons.
   - Otherwise collect a reason for each breach: month-to-date spend plus the estimate strictly over `monthly_usd` (the reason mentions "monthly"), and the estimate strictly over a non-null `max_run_usd` (the reason mentions "per-run cap").
   - `"block"`: allowed only when there are no reasons. `"alert"`: always allowed, but the reasons are still returned — silent truncation reads as "nothing to see" when there was.

## CLI

Keep `ledger budgets --month M --budgets F [--history H]` working exactly as today for existing scripts (it should not alert on `off` pipelines). Add:

- `ledger budget-set PIPELINE --budgets F [--monthly-usd N|inherit] [--enforce alert|block|off|inherit] [--max-run-usd N|inherit]` — creates the pipeline entry if needed, `inherit` writes `null`, untouched fields are left as they are, and the file is saved as version 2.
- `ledger budget-reset --budgets F --field FIELD --pipelines a,b,c` — `reset_to_inherit` over the listed pipelines; prints `reset N pipeline(s)`.
- `ledger budget-summary --budgets F --month M [--history H]` — first line exactly `default monthly budget $500.00 governs 2 of 5 pipelines`, where the universe is every pipeline in the config plus every pipeline with history in that month, followed by one line per pipeline (`name`, resolved monthly budget, and `inherited` or `override`).

## Constraints

- Stdlib only. Update the `ledger.budget` docstring (it documents the file format) and the ledger README in the same change.
- Do not mass-rewrite a version-1 file on load; only `save_budgets` (via the CLI commands that change something) writes.
- Unit tests for policy resolution are essential: especially that `null` and a missing key inherit, that `0` does not, and that `off` is never alerted or blocked.
- `python -m pytest -q` at the root stays green.

Report back what you built for each part, how a version-1 file converts, and anything you deliberately did not do.
