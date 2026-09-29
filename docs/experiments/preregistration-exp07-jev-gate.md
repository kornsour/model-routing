# Pre-registration: exp07, a decision-model gate (Jev)

Status: **draft, not yet registered.** Every run is exploratory until the
gates in "Before registering" are met.

exp07 is a separate experiment with its own registration. It tests whether a
third-party decision model (Jev) helps. The exp06 hypothesis does not depend
on it, and no exp07 result changes an exp06 verdict. No registered field of
exp05 or exp06 changes because of exp07.

**Shared protocol.** To avoid a second task set and a second calibration,
exp07 reuses the protocol in `docs/paper/exp06-route-on-evidence.md` (v0.3)
wherever this document is silent: the control, the H0 headroom gate and its
stopping rule, the strata, calibration at 3 trials, the grouped tuning and
confirmatory splits, the paired randomized block design, the 40-turn cap and
its sensitivity analysis, the per-task majority oracle, intention to treat
with outages redone, analyst blinding, one run at a time, and the budget
priority rule. This document adds only what a decision model changes.

## Question

Inside the exp06 ladder, does a decision model add anything as (a) the
verifier that triggers a handoff, or (b) a prompt-only router, compared with
what exp06 already uses in those two places?

## Order of work

exp07 runs only after exp06's Stage 0 has passed H0. If exp06 stops at H0,
exp07 stops too: a gate cannot earn anything on work with no headroom. On
exp05's task set a perfect, free Haiku-then-Sonnet gate costs $0.221 per
completed task against $0.099 for always Sonnet.

## Arms (added to exp06's)

| Arm | What happens | Compared with |
|---|---|---|
| `explore_handoff_clean_jev` | as `explore_handoff_clean`, but the L3 trigger's verifier is visible tests, scope check and the Jev risk questions, with no generated test pass | `explore_handoff_clean` |
| `C2_jev` | Jev picks the model from the brief alone; below `min_confidence` it falls back to the mid-tier default | `C2_trained`, `explore_handoff_clean` |
| `random_matched` | as in exp06, at the Jev arm's observed handoff rate | computed from the static arms, not run |

Required from exp06 in the same run: `static_sonnet`, `static_opus`,
`explore_handoff_clean`, `ladder_ideal`.

## Hypotheses

Primary:

**J1 (the Jev verifier catches what the free signals miss).** Among
mid-tier attempts that the free signals would accept (no session error,
visible tests pass, evidence complete), the larger of the two Jev risk
values separates failed from passed attempts: the AUROC interval's lower
bound is above 0.5, labels from the hidden grader run after the decision.

Secondary, Holm-adjusted as one family:

| # | Hypothesis | Comparison |
|---|---|---|
| J2 | The Jev verifier has a lower false-accept rate than exp06's verifier, at a handoff precision no more than 10 points worse. | `explore_handoff_clean_jev` vs `explore_handoff_clean` |
| J3 | On the measured hard stratum the Jev arm's completion is non-inferior to exp06's handoff arm within 10 points, at a lower cost per completed task over the whole set. | same pair |
| J4 | The Jev trigger beats handing off at random at the same rate. | Jev arm vs `random_matched` |
| J5 | exp06's L3 prediction holds against a decision model too: evidence beats a prompt-only pick. | `explore_handoff_clean` vs `C2_jev` |

What would refute J1: an AUROC interval that includes or lies below 0.5.
J2 to J5 follow exp06's interval rules.

Gate quality is reported for every verifier with task-clustered intervals:
false-accept rate, false-handoff rate, recall and precision against measured
need, failure rate per 0.2-wide band of the risk score, and the Brier score.
The Jev questions ask about missing requirements and contradicted completion
claims, not "will the hidden tests fail", so reliability against the failure
label describes the gate as used. It is not a test of the vendor's
calibration claim.

## Frozen gate inputs

| Field | Value at registration |
|---|---|
| Gate model | `jev-1.13.0`, never an alias; the adapter rejects a response naming another model |
| Question text and criteria | as in `src/model_routing/dispatch/jev_policies.py` at the registered harness commit |
| State fields and limits | brief, change evidence (24,000 characters), last 4,000 characters of worker output and of the visible result |
| `risk_threshold`, `min_confidence` | fitted on exp06's tuning split only |
| Retries | none |

These rows are added to exp06's Appendix A table for the exp07 registration.

Repeatability is measured before registration: 20 fixed requests sent 5
times each. If identical requests return different answers, the spread is
reported.

## Rules specific to a third-party gate

- **Data leaving the machine.** exp06's first task source is handoffs
  harvested from the operator's own transcripts. Those briefs and the diffs
  produced on them would be sent to TypeSafe by every Jev call. The Jev arms
  run only on strata cleared for that (see "Open decisions"). Tasks under
  `tasks/agentic/private/` are never sent.
- **Gate failures.** An HTTP error, timeout, invalid response or rate limit
  is part of the policy: the arm hands off, the call is billed at the
  64,000-token upper bound, and the cell is graded. The gate error rate is
  reported. Worker-provider outages are redone, as in exp06.
- **Billing.** Gate calls are `role = "router"` and count toward cost per
  completed task. A price row for `jev-1.13.0` exists before any run.
- **Isolation.** exp07 never runs at the same time as exp06 or any other
  run (exp06 Section 7.3).

## Sample size

exp07 does not set its own task count. It uses exp06's confirmatory split
and its power method (exp06 Section 7.5).
J1 needs failed mid-tier attempts that the free signals accepted: about 80
give a rate near 70% to within ±10 points before clustering. exp05's Haiku
arm had a within-task correlation of 0.51 across 3 trials, a design effect
of about 2, so the count of distinct tasks matters more than the count of
trials. If the confirmatory split yields fewer than 40 such tasks, J1 is
reported descriptively with no verdict.

## Threats to validity

| Threat | Handling |
|---|---|
| Worker text steering the gate (the vendor states Jev does not treat state as hostile) | the instructions tell the gate to treat state as evidence; false accepts are inspected for completion claims in the worker output |
| Accuracy falling with long state | evidence is bounded; truncation forces a handoff and its rate is reported |
| Vendor claims on calibration and latency | not assumed; only measured values are reported |
| One gate version, early access | stated as scope; the result is about `jev-1.13.0` |
| No LLM verifier answering the same questions | the claim is limited to a decision-model gate against exp06's verifier |

## Before registering (gates)

1. exp06 Stage 0 complete and H0 met.
2. Thresholds fitted on the tuning split and written into the config.
3. Repeatability measured.
4. Smoke run on real models showing a Jev-triggered handoff, a Jev accept
   and a gate failure, on at least two hard tasks.
5. The report checks the frozen gate inputs and prints the gate-quality
   table and the matched-rate baseline.
6. `make dispatch-estimate` within budget, `--budget-usd` set, and the
   operator's go-ahead. Register, commit, then run.

## Open decisions (operator)

| Decision | Proposed | Alternative |
|---|---|---|
| Which strata may be sent to TypeSafe | fixture-repo strata only | also the harvested handoffs, after the operator reviews them for private content |
| Build a Haiku verifier answering the same two questions | yes | no, and the claim stays narrower |
| Run `C2_jev` | yes, it costs gate calls plus one worker session per cell | drop it first if the budget binds |

## Deviations

None. Not yet registered.
