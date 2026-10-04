# Pre-registration: exp07, an evidence-gated advisor instruction

Status: **draft, not yet registered (2026-10-02).** Every run is exploratory
until the gates in "Before registering" are met. exp07 runs before exp08
(the Jev gate, `../exp08-jev-gate/preregistration.md`); the two are
separate experiments with separate registrations and budgets.

## Why this experiment exists

exp06 measured what a frontier advisor costs when the work does not need
it (`../exp06-route-on-evidence/results.md`, v1.2, Section 4). With the
advisor available, Sonnet 5.5 consulted it on 42% to 76% of easy tasks, at
about $0.26 a consultation, and every advisor arm cost 1.85× to 2.63× plain
Sonnet for the same completion. Those figures come from the 15 first-batch
tasks.

A design review of the follow-up study found that exp06's own worker
instruction asks for those consultations (`LADDER_ADVISOR_NOTE` in
`src/model_routing/dispatch/policies.py`): "Consult it before committing to
an approach, when an error keeps recurring, and **always before you
declare the task done**." Before paying for any external gate, the cheapest
explanation has to be ruled out: the over-consultation is the instruction's
doing, and rewording it removes most of the idle cost.

## Question

If the advisor instruction allows consultation only on evidence (a check
that still fails after the worker tried to fix it, or an error that
recurs), does an advisor-equipped Sonnet session cost close to plain
Sonnet on easy work, without losing completion?

## Shared protocol

exp07 inherits the exp06 protocol (`../exp06-route-on-evidence/paper.md`,
v0.3) wherever this document is silent:
- the paired randomized block design and 3 trials;
- the turn caps (40, and 80 for the long-horizon stratum);
- intention to treat, with provider outages redone;
- task-clustered bootstrap intervals and analyst blinding;
- one paid run at a time, an hour after any other.

There is no headroom gate and no tuning split, because nothing is fitted to
tasks.

## Task set

The pooled exp06 set, frozen at its current hash: `tasks/exp06/tasks.jsonl`
and `tasks/exp06/tasks_ext.jsonl`, minus the 3 unsolved tasks, which leaves
**52 tasks**. The difficulty labels are the measured exp06 labels:
- **45 easy.** These are the primary set.
- **2 medium and 5 hard.** These are reported descriptively only.

## Arms

| Arm | Worker instruction | Everything else |
| --- | --- | --- |
| `static_sonnet` | none (no advisor) | Sonnet 5.5, no verifier, no handoff; the control |
| `ladder_noforce` | exp06's `LADDER_ADVISOR_NOTE`, unchanged | as in exp06: Opus 5.5 advisor, deployable verifier, K = 2, clean handoff, `ESCALATE` honoured, no forced check |
| `ladder_evidence` | **evidence-gated note** (below) | identical to `ladder_noforce` |

The two advisor arms differ in **one sentence of the worker prompt and
nothing else**. They share the advisor, verifier, handoff and escalation
note, and both run the request-logging hook (below).

**Evidence-gated note (frozen wording):** "- You have an advisor tool
backed by a stronger model. Consult it only when you have evidence you
cannot resolve alone: a check that still fails after you have tried to fix
it, or the same error recurring. Do not consult it to confirm an approach
or before finishing."

**Request log.** A `PreToolUse` hook on the advisor tool, in pass-through
mode, records every advisor request: task, trial, turn, the question text,
and a snapshot of the state a gate would see. The snapshot holds:
- the brief;
- the diff, at most the first 24,000 characters;
- the last 4,000 characters of worker output and of visible test output.

The hook never blocks a request. The log has two uses: the request-level
analysis below, and exp08's offline replay. Hidden tests are never in the
sandbox, so they cannot appear in the log.

## Outcomes and hypotheses

Cost per completed task includes every session the policy spends (advisor
tokens, verifier reruns, handoff sessions), priced from `pricing.toml`.

**Primary. E1 (the instruction drives the idle cost).** On the 45 easy
tasks, `ladder_evidence` has a lower cost per completed task than
`ladder_noforce`, with completion non-inferior to `ladder_noforce`. Both
parts must hold:
- **Cost:** the one-sided 97.5% upper bound of the cost ratio is below 1.0.
- **Completion:** the one-sided 97.5% lower bound of the paired completion
  difference is above −5 points.

Secondary, Holm-adjusted as one family of two:

| # | Hypothesis | Test |
| --- | --- | --- |
| E2 | The evidence-gated advisor is close to free when idle: `ladder_evidence` cost per completed task on easy tasks is at most 1.25× `static_sonnet`. | upper 97.5% bound of the ratio below 1.25 |
| E3 | The instruction changes **why** the worker consults: a larger share of `ladder_evidence` requests carry the evidence rule label than of `ladder_noforce` requests. | difference in shares, task-clustered, lower bound above 0 |

**Verdicts.**
- **Supported:** the interval clears the bound.
- **Not supported:** the interval lies wholly on the wrong side of the bound.
- **Inconclusive:** anything else, reported as inconclusive with the interval.

There is no other verdict.

**The evidence rule label (frozen, deterministic).** A logged request is
labelled `evidence_present` when the last 4,000 characters of output before
the request contain either of the following (regexes frozen in the harness
at registration):
- a failing test or verifier result, recognised by pytest, `go test` or
  `node --test` failure markers;
- the same error line twice.

It is a label for **what the worker had seen**, not ground truth about
need. Every claim about it is worded that way.

**Planning values, stated before any run.**
- **E1's cost ratio:**
  - exp06 measured `ladder_noforce` at 1.85× plain Sonnet, interval
    [1.57, 2.16], on 14 easy tasks.
  - The handoff-only arm, which had no advisor, measured 1.00×, interval
    [0.93, 1.10].
  - Rescaled to 45 tasks, the expected half-width of the cost ratio is
    about 0.15 for an advisor arm and 0.05 for a near-static arm.
  - If `ladder_evidence` lands near 1.1× plain Sonnet, then E1's ratio is
    about 0.6 with an upper bound well below 1.0. E1 is powered.
- **E2:** a true ratio of 1.10 gives an upper bound near 1.20. E2 is
  powered only if the instruction removes most consultations. The 1.25
  bound is half of exp06's 1.5 allowance: the idle overhead of a safety net
  that, on exp06's evidence, almost never has hard work to rescue.
- These planning values are recomputed from the exp06 cell data and
  recorded here before registration (below).

**Planning values, recomputed 2026-10-04 (gate 3).** Method: the 14 easy
first-batch tasks of the exp06 ladder run
(`results/exp06_ladder/20260930-044605`), resampled to 45 tasks with
replacement (each task keeps its 3 cells), 2,000 draws; the median and the
2.5/97.5 percentiles of the statistic are the expected estimate and interval
at 45 tasks. Sonnet's cost comes from both exp06 calibration runs on the 52
tasks.

| Quantity | 14 tasks (measured) | 45 tasks (projected) | Half-width at 45 |
| --- | --- | --- | --- |
| `ladder_noforce` / `static_sonnet`, cost ratio | 1.85 [1.57, 2.16] | 1.85 [1.68, 2.02] | 0.17 |
| no-advisor handoff arm / `static_sonnet`, cost ratio | 1.00 [0.93, 1.10] | 1.00 [0.96, 1.05] | 0.05 |
| no-advisor handoff arm / `ladder_noforce`, cost ratio (E1 if the note removes nearly every consultation) | 0.54 [0.47, 0.63] | 0.54 [0.50, 0.59] | 0.05 |
| completion, no-advisor handoff arm − `ladder_noforce` (points) | −2.4 [−7.1, 0.0] | −2.2 [−5.2, 0.0] | 2.6 |

What follows from them:
- **E1 cost** is powered: it is supported if the evidence note brings
  `ladder_evidence` to about 0.9× `ladder_noforce` or below.
- **E1 completion is the weak part.** Both arms complete close to 100% of
  easy tasks, so one or two failed cells move the lower bound across −5:
  the projection's lower bound is −5.2. A completion verdict of
  "inconclusive" is a likely outcome even if the note costs nothing in
  quality. The −5 margin is unchanged; this is recorded so that the
  outcome is not a surprise.
- **E2** is powered if `ladder_evidence` comes in under about 1.15× plain
  Sonnet (half-width about 0.05 to 0.1).
- **Consultation rates in exp06 (easy, first batch):** `ladder_noforce`
  consulted voluntarily in 62% of cells, 0.79 calls per cell, $0.515 per
  cell; plain Sonnet $0.271.
- **Cost:** plain Sonnet averages $0.252 per cell on the 52 tasks, so about
  $40 for 156 cells; `ladder_noforce` at about 1.9× is about $75;
  `ladder_evidence` between 1.0× and 1.5× is $40 to $60.

**Few-events rule.** E3 needs requests in both arms. If `ladder_evidence`
logs fewer than 20 requests on easy tasks, E3 is reported descriptively,
with no verdict. That outcome would also mean E1 is very likely supported.

**Descriptive, no verdict.**
- **Per arm:**
  - requests per session, as a distribution;
  - the advisor's share of cost;
  - the handoff rate and the `ESCALATE` rate. The evidence note may push
    the worker toward a full handoff instead of a consultation, and that
    cost is already inside cost per completed task.
- **On the 7 hard and medium tasks:** completion per arm, listed per cell,
  with static Sonnet's calibrated pass rate shown beside it as the chance
  baseline.
- **The full request table:** one row per logged request, with task,
  trial, turn, arm and rule label.

## What this experiment can and cannot claim

It can claim, with intervals:
- "On 45 easy coding tasks, changing one sentence of the advisor
  instruction changed cost per completed task from X× to Y× plain Sonnet,
  at completion within M points."
- "That change raised the share of advisor requests made after a visible
  failure from A% to B%."

It cannot claim:
- that the advisor helps on hard work, since there are only 7 hard or
  medium tasks;
- that the rule label marks needed requests;
- anything about other harnesses, vendors, or tasks not written by the
  Claude family.

## Frozen at registration

| Field | Value |
| --- | --- |
| Models | `claude-sonnet-5-5`, advisor `claude-opus-5-5`, exact ids |
| Claude Code version | one version for the whole run, recorded per session; a version change mid-run is a deviation |
| Worker instructions | both advisor notes, verbatim, at the registered harness commit |
| Hook and request log format | harness commit |
| Rule-label regexes | harness commit |
| Analysis | an `exp07` analysis module implementing E1 to E3 and the descriptive tables, committed, hashed into the config, and dry-run on the fake provider before registration |
| Task set | the two `tasks/exp06/` files, by hash |
| Seed, order | randomized block order, seed in the config |

## Threats to validity

| Threat | Handling |
| --- | --- |
| Mostly easy tasks, written by the model family under test | stated as scope; easy work is the regime the question is about |
| The arms differ in more than the instruction | identical config apart from the note; the hook runs in both |
| Model or CLI drift during the run | randomized block order across arms; one pinned CLI version; exact model ids |
| A no-advisor arm would beat both advisor arms | expected; `static_sonnet` is reported so that comparison is never hidden |
| The rule label is read as "need" | worded as "evidence the worker had seen" throughout |

## Before registering (gates)

1. The hook records requests in headless mode on a smoke run, without
   changing the advisor's cost on that run. A smoke run with the hook
   disabled is the comparison.
2. The exp07 analysis module is dry-run on the fake provider.
3. Planning values are recomputed from exp06 cells and recorded here.
4. A pilot of 5 tasks × 1 trial for each advisor arm (about $5), excluded
   from analysis, to check request logging and the label regexes.
5. `make dispatch-estimate`, then `--budget-usd` set, then the operator's
   go-ahead. Register, commit, then run.
6. **One Claude Code version:** `make cli-freeze` before the first paid
   check, and **`make cli-unfreeze` as soon as the experiment's last run
   ends** (or is abandoned). The runner also sets `DISABLE_AUTOUPDATER=1` on
   every CLI session and stops between cells if the CLI version changes.

**Gate status (2026-10-04).**

| Gate | Status |
| --- | --- |
| 1. Hook smoke | Built, not run. The hook (`model_routing.dispatch.advisor_log`) is a pass-through `PreToolUse` command installed with `--settings`; it is unverified whether Claude Code runs it for the server-side advisor tool. If it does not fire, requests still come from the session's stream-json (turn, recent output, label) and only the diff is missing, which exp08's replay needs. Config: `experiments/exp07-evidence-prompt/exp07_hook_smoke.toml` (2 tasks × 1 trial, hook on and off). |
| 2. Analysis dry run | Done. `model_routing.dispatch.exp07` on a full fake run of `exp07.toml` (468 cells): every table and verdict computes. Fake numbers are meaningless (the fake agent never consults or writes `.verifier` tests). |
| 3. Planning values | Done (above). |
| 4. Pilot | Config ready (`exp07_pilot.toml`: 5 tasks × 1 trial, both advisor arms); not run. |
| 5. Estimate, budget, go-ahead | Waiting for the operator. |
| 6. CLI frozen | Frozen at Claude Code 2.1.285 since 2026-10-04. |

**Task-set note found by gate 2.** One extension fixture failed to build
in a fresh checkout: `tasks/exp06/history/ha-branch-triage-02.sh` moves a
file into `docs/archive/`, which existed only as an empty, untracked
directory in the worktree where the task set was authored and calibrated
(git does not record empty directories). The script now creates the
directory first, which reproduces the calibrated state exactly; all 55
tasks validate from a fresh checkout. Three other empty directories existed
only in that worktree (`github-private/.github/workflows`,
`packlight-app/public`, `platform/docs`); they change nothing a grader
checks and are not recreated.

## Sample size and budget

52 tasks × 3 trials × 3 arms = 468 cells. Expected list cost:
- `static_sonnet`: about $45;
- `ladder_noforce`: about $80;
- `ladder_evidence`: about $50 to $65;
- pilot: about $5.

That is **$180 to $195**, within the roughly $225 left of the $500 study
budget. Budget priority if a pause hits: finish `ladder_evidence`, then
`ladder_noforce`, then `static_sonnet`. A `static_sonnet` shortfall can
fall back to exp06's two fresh Sonnet runs, as a recorded deviation.

## Design review

Reviewed 2026-10-02 by a separate model instance (Claude Fable 5.1),
against the combined gate draft. The review found that the standing
"always before you declare the task done" instruction confounds any gate
with the prompt it overrides. That finding is why this experiment was
split out and runs first.

Its points taken here:
- one-sided non-inferiority;
- the inconclusive band;
- planning values;
- the few-events rule;
- the deterministic rule label in place of "need";
- the frozen analysis module;
- one CLI version;
- the pilot;
- the full request table.

## Deviations

None. Not yet registered.
