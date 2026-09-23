# Pre-registration and analysis plan: exp05 dispatch-time routing

Status: **draft, not yet registered.** The `[preregistration]` table is
appended to `experiments/agentic/exp05_dispatch.toml` by
`make dispatch-preregister EXP=experiments/agentic/exp05_dispatch.toml WRITE=1`
only after the gates in "Before registering" are met. Until then every run
is exploratory and the report says so.

This document is what a reviewer should be able to check the confirmatory
run against. Anything here that changes after registration must be recorded
under "Deviations" with the date and the reason, and the run is then
exploratory again.

## Question

When an assistant session hands work off to a fresh agent session (a task
chip, a subagent), does letting the parent pick the worker model reduce the
cost per completed task without a meaningful drop in the completion rate?

## Primary hypothesis (H-D1)

`C1_inline` (the parent writes the brief and the model choice in one turn;
only the pick's marginal tokens are billed as router overhead) has a lower
cost per completed task than `B` (spawn on the parent's own model), and its
pass rate is non-inferior to `B` within the margin.

- **Primary metric:** cost per completed task, list price from
  `src/model_routing/data/pricing.toml`, summed over worker, router and
  escalation sessions. Parent-seeding sessions are a sunk cost and excluded.
- **Quality metric:** pass rate under the deterministic grader (hidden tests
  pass, visible tests still pass, nothing outside the allowed scope changed).
- **Non-inferiority margin:** 10 percentage points. Decided 2026-09-23 before
  any confirmatory data. Reason: the pilot's C1 and B outcomes disagreed on
  33% of paired task-trials; at that discordance a 5-pt margin needs about
  1,000 paired task-trials (about $600-1,200), a 10-pt margin about 260. Ten
  points still answers the business question ("does it save real money
  without a noticeable quality drop?") at a cost worth paying.
- **Design:** paired. Every sampled task runs under every selected policy for
  the same number of trials. Trials = 3.
- **Ordering:** randomized block design. For each (task, trial) block the
  selected policies run in a seeded random order (`order = "randomized"`,
  `seed` in the config), so no policy is systematically first or last in
  wall-clock time. Sessions are strictly sequential; nothing runs in
  parallel.
- **Turn cap:** 40 turns per session for every policy (the pilot used up to
  23). The per-task `max_turns` field in `tasks.jsonl` is a human guess and
  is not used.
- **Blinding:** no policy reads a task's difficulty label; the router only
  sees the brief (and, for `C1*`, the parent context). Graders are
  deterministic; there is no LLM judge.

## Decision rule (fixed)

Computed by `model_routing.dispatch.report.summarize`:

- 95% task-clustered bootstrap intervals (2,000 draws; all trials of a task
  are resampled together) for the paired pass-rate difference (points) and
  for the saving fraction `1 − cpt(C1_inline) / cpt(B)`.
- **Non-inferior** if the lower bound of the pass-rate difference exceeds
  −10 points.
- **Real saving** if the whole saving interval lies above zero.
- Verdict `supported` = non-inferior and real saving; `not supported` = the
  upper bound of the pass-rate difference is below −10, or the whole saving
  interval lies below zero; otherwise `inconclusive`.
- Reported alongside, with no role in the verdict: a two-sided task-clustered
  permutation p-value for the cost ratio (log scale) and for the pass-rate
  difference, and a one-sided bootstrap p-value for "worse by at least the
  margin". Conventional threshold for a reader: 0.05 (the verdict's interval
  rule is equivalent to a one-sided 2.5% non-inferiority test).

## Sample size

Paired non-inferiority (McNemar approximation, true difference 0):
`n ≈ (z_α + z_β)² · p_disc / δ²` with `z_α = 1.96`, `z_β = 0.84`, `δ = 0.10`.

| discordance | paired task-trials | tasks at 3 trials |
|---:|---:|---:|
| 17% (fake sim) | 131 | 44 |
| 25% | 196 | 66 |
| 33% (pilot) | 260 | 87 |

Registered target: **≥ 60 tasks × 3 trials = 180 paired task-trials**,
measured discordance permitting; if the calibration run shows discordance
above 25%, raise the task count to 90 before registering. The report's
power note recomputes this from the observed discordance.

Estimated spend (`make dispatch-estimate`, profiles from observed sessions):

| policies | 60 tasks × 3 | 90 tasks × 3 |
|---|---:|---:|
| `B`, `C1_inline` (primary only) | about $70 | about $105 |
| + `static_haiku`, `static_sonnet` (oracle, H-D7) | about $105 | about $160 |
| + `C1`, `D` (H-D4, pessimistic C1) | about $185 | about $280 |
| all 12 policies | about $380 | about $570 |

The confirmatory run must include at least `B`, `C1_inline`, `static_haiku`
and `static_sonnet`. Secondary policies may be dropped for budget; that is
not a deviation for H-D1.

## Secondary hypotheses (exploratory)

H-D2 to H-D7 as listed in `docs/experiments/dispatch-routing.md`. They are
reported with Holm-adjusted p-values across the family and are hypothesis
generating, not confirmatory. `C1` (forked router that re-reads the parent
context) is kept as the pessimistic routing variant.

## Task set

- Source: `tasks/agentic/tasks.jsonl` and its `repos/`, `hidden/`, `setup/`,
  `mutants/`, `solutions/` directories. The whole tree is hashed into
  `taskset_sha256`; the report refuses to call a run confirmatory if the
  hash differs from the registered one.
- Difficulty labels are **measured**, not guessed: a calibration run of every
  task on every static candidate (`experiments/agentic/exp05_calibrate.toml`,
  3 trials) is folded by `make dispatch-calibration ... WRITE=1` into
  `difficulty` (easy = the cheapest model passed every trial, medium = it
  passed some, hard = only the strongest passed, unsolved = nothing passed).
  Unsolved tasks are removed or fixed before registration.
- Headroom gate: the cheapest model passes about 50-70% of the registered
  set, the middle model more, the strongest most. A set the cheapest model
  passes outright makes "always cheapest" optimal by definition and cannot
  test routing.
- Sampling: if fewer than all tasks are run, the sample is a seeded,
  difficulty-stratified draw (`seed` in the config; the manifest is in
  `meta.json`).

## Inclusion and exclusion (intention to treat)

- Every planned (task, policy, trial) cell counts once. A session that ends
  in a provider error (timeout, budget cap, non-zero exit) is graded on
  whatever state the sandbox is in and its cost is counted; the report
  shows the error rate per policy.
- A run stopped by the budget guard is reported as `over_budget` and is not
  confirmatory unless every registered cell completed.
- No cell is re-run or dropped after the fact. If a task is found to be
  defective (e.g. its hidden test is wrong), the whole task is excluded from
  every policy, the exclusion is recorded under "Deviations", and the run is
  exploratory.

## Replication

- Three trials per cell within the run; the report clusters them by task.
- A second vendor track with the same design
  (`experiments/agentic/exp05_dispatch_codex.toml`) is a replication of the
  question on a different model family, not part of H-D1.
- `meta.json` records the harness git SHA, config hash, task-set hash, seed,
  CLI versions, and every session's resolved model id, so the run can be
  reproduced and re-priced.

## Before registering (gates)

1. Task set at ≥ 60 tasks, every task validated (`make check`), calibrated
   with 3 trials, relabelled, headroom gate met.
2. Smoke run of the untested paths on real models
   (`experiments/agentic/exp05_smoke_paths.toml`): `A`, `A_switch`,
   `C1_inline`, and `D` escalating at least once. Surprises recorded in
   `docs/experiments/findings/`. Status 2026-09-23: `A`, `A_switch` and
   `C1_inline` verified (`findings/2026-09-23-exp05-smoke-paths.md`); `D`
   escalation still to be exercised on a task the cheapest model fails.
3. `make dispatch-estimate` for the registered policies within budget.
4. `make dispatch-preregister ... WRITE=1`, commit, then run.

## Deviations

(none yet)
