---
title: Work the platform incident queue
terse: Reproduce and fix the eight open incidents against orchestra and ledger at their root causes, and leave alone any that turn out to be documented behaviour.
repo: platform
parent: platform
allowed: ["packages/orchestra/*", "packages/ledger/*", "packages/toolbelt/*", "docs/*", "README.md"]
category: bugfix
tags: [long-horizon, multi-package, debugging, triage]
stratum: B
max_turns: 80
harvest_shape: "several reported failures with partial prior findings, a root-cause-not-symptom rule and a 'legitimate result: not a bug' escape (harvested #12 and #18: diagnose before fixing, don't paper over)"
authorship: "Brief drafted from the shape of harvested debugging dispatches by Claude Opus 5.5; fixture (with injected defects), hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
The platform on-call queue has eight open incidents against `orchestra` and `ledger`. I need them worked to closure in one pass: you are in the `platform` monorepo (current directory) and `python -m pytest -q` runs every suite (it is green, which is part of the problem: the tests that should have caught some of these were weakened at some point).

## Ground rules

- **Reproduce first.** For each incident, write a test that fails for the reported reason before you change any code, in the owning package's `tests/`. If you cannot make it fail, the incident may be working as documented.
- **Fix the root cause, not the symptom.** Several symptoms show up in `ledger` but may originate in `orchestra` (or the other way round). The module docstrings are the contract: `orchestra.scheduler`'s docstring for scheduling, `orchestra.events` for replay, `ledger.pricing`, `ledger.store`, `ledger.inflight` and `ledger.budget` for theirs. Where code and docstring disagree, the docstring wins unless it is clearly the thing that is wrong — say which in your report.
- **At least one incident may be documented behaviour.** If so, do not change it: add a test that pins the documented behaviour and explain in your report why it is correct. "Not a bug" is a legitimate, valuable result.
- Keep each fix minimal. Strengthen any weakened test you come across so it would have caught the bug.

## The incidents

1. **INC-4101 — one attempt too many.** `load_orders` has `max_attempts: 3`. Last night's event log shows four `start` events for it before it was marked `failed`.
2. **INC-4102 — wrong culprit in the reason.** `publish_report` depends on `extract_orders` then `extract_inventory` (in that order in its spec). Both failed. Its `upstream_failed` reason says `upstream extract_inventory failed`; the on-call engineer chased the wrong job for an hour.
3. **INC-4103 — stale "retrying" on the dashboard.** The dashboard rebuilds state from the event log. A job that failed its first attempt and was already running its second attempt showed "retrying at 02:14" for the whole second attempt.
4. **INC-4104 — retries are free.** `load_orders` failed twice and succeeded on its third attempt (three 20-minute attempts on 2 warehouse slots). The ledger billed one attempt's worth.
5. **INC-4105 — September run in October's report.** The Berlin runner recorded a run with `started_at` `2026-10-01T01:30:00+02:00` (23:30 UTC on 30 September). It appears in October's monthly report and not September's. Finance's months are UTC months.
6. **INC-4106 — hourly skipped all night.** While a long `nightly` run was in flight, the scheduler skipped every `hourly` run with "already running".
7. **INC-4107 — alert at exactly the budget.** `ledger budgets` printed `OVER nightly: $200.00 of $200.00`.
8. **INC-4108 — makespan 0 for the noop pipeline.** A run of the `noop` pipeline (three jobs, all `duration: 0`, all succeeded) reported `makespan 0.0`. The reporter expected a positive number "since three jobs ran".

## Report back

Per incident: the root cause (file and function), the fix, the reproducing test, or for a documented-behaviour incident the reasoning and the pinning test. Also list each test you strengthened.
