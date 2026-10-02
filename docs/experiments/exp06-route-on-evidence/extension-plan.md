# exp06 Stage 0 extension: one more draw for frontier-only work

Status: **run 2026-10-01/02; H0 not met (5 of 55 hard pooled); exp06
closed.** Task set: `findings/2026-10-01-exp06-stage0-ext-taskset.md`.
Result: `findings/2026-10-02-exp06-stage0-ext.md` and `results.md` v1.2.
The "If H0 fails" branch below is the one taken. Written 2026-10-01 after the first Stage 0 batch
(`findings/2026-09-30-exp06-stage0.md`) and the results paper
(`results.md`, v1.1) found no measured-hard task.

## Why this run exists

The v0.3 protocol (`paper.md` Section 3) makes H0 a stopping rule with one
allowed extension: if calibration finds too little headroom, "the fix is to
draw more tasks from the sources above (one extension allowed), not to
hand-pick failures" (Section 7.1). The first batch produced 0 hard tasks
against a bar of 10. This is the one extension.

It is a **Stage 0 only** run: Sonnet 5.5 and Opus 5.5 on every new task,
3 trials each, nothing else (Haiku is dropped; see "Run"). The ladder arms are not re-run on
easy work; their idle cost is already measured (`results.md` Section 4) and
a second idle-cost run would add nothing. Ladder arms run again only if H0
passes on the pooled set.

## What the first batch answered, and what this run is for

| question | first batch | this run |
|---|---|---|
| Idle cost of each rung on easy work (L1 c2, c3) | answered: handoff 1.00×, advisor 1.85×, full ladder 2.63× plain Sonnet | not re-tested |
| Over-escalation on easy work (L2 precision) | answered: 42% to 76% voluntary advisor calls, precision 0% | not re-tested |
| Is there frontier-only work in long, single-session, fully specified coding tasks written by an Opus-class model? | answered: no (0 of 15) | not re-tested |
| Is there frontier-only work in **drawn** work: real handoffs, long-horizon and multi-repo tasks, ambiguous briefs, non-coding work? | **not tested**; those strata were never built | **this run** |
| Everything that needs hard tasks (L1 c1, L2 recall, L4, L5, L6) | open | open until H0 passes |

The first batch's main validity threat was its task source: 15 tasks,
written from scratch by the model family under test, all shaped to fit one
40-turn session with a complete specification. This run changes the source
and the shape. It does not change the bar.

## Task sources

Drawn or derived, in the protocol's priority order. **No task is added
because a mid-tier model failed it in a trial run.** Every task is built,
validated and frozen before any model is run on it.

| stratum | count | source | grader | notes |
|---|---:|---|---|---|
| **A. Harvested handoffs** | 16 | seeded random draw from the 562 prompts in `tasks/agentic/private/harvested.jsonl` (`make harvest-chips`), converted to fixture tasks | hidden tests, `allowed_paths` | brief kept at its real length and wording, with project-specific names replaced; a drawn prompt is skipped and the next drawn only when no deterministic grader can be written or the content is private; the skip count and reasons are recorded |
| **B. Long-horizon and multi-repo** | 12 | tasks spanning both fixture repos or several modules of one, with briefs of 1,000 to 2,500 tokens shaped like real subagent dispatches (background, prior findings, numbered steps) | hidden tests, `allowed_paths` | `max_turns` 80 for this stratum; the 40-turn figure is reported as a sensitivity row |
| **C. Ambiguous briefs** | 6 | fixture tasks with one deliberately missing requirement and a scripted answer key for clarifying questions | hidden tests pin the keyed interpretation | calibration runs the static arms without a simulated user; the answer key is for L5 later. Section 7.1 item 3 |
| **D. Non-coding and read-only investigation** | 6 | questions about a fixture repo answered in a fixed, parseable format | answer key plus an empty-diff scope check | the chip harvest's recommendation 4; about 10% of real dispatches are read-only |
| **total new** | **40** | | | pooled set 55 |

**Authorship.** The first batch's tasks and reference solutions were written
by an Opus-class assistant, the family under test. For this batch:

- Stratum A briefs are the harvested text, not written. Fixture conversion
  is done by the operator with assistant help; the assisting model is recorded
  per task.
- Strata B, C and D briefs are drafted from harvested dispatches of the same
  shape, not from scratch.
- Reference solutions and hidden tests are written or independently
  re-derived by a model from a different family (`codex exec` is already a
  harness provider) where that is practical; where not, the fact is recorded
  in the task's front matter. The untouched repo must fail the hidden tests
  and the reference solution must pass them, as the validator already checks.

**Brief statistics.** After building, re-run `scripts/chip_stats.py` on the
new briefs and record the comparison as a findings note, per the chip
harvest's recommendation 6. Target: median brief length near the real
`spawn_task` median (about 500 tokens) for stratum A and the real dispatch
range for stratum B.

## Run

Config: `experiments/exp06-route-on-evidence/exp06_calibrate_ext.toml`,
copied from `exp06_calibrate.toml` with the new task file, a new seed,
per-stratum `max_turns` (`per_task_max_turns = true`, the caps live in the
task file), and the `static_haiku` policy removed. Models pinned by exact id; Claude Code version
recorded. Randomized block order, sequential, one run at a time, one hour
after any other paid run.

```bash
uv run python tasks/exp06/build_tasks.py
make dispatch-estimate EXP=experiments/exp06-route-on-evidence/exp06_calibrate_ext.toml
make dispatch-run EXP=experiments/exp06-route-on-evidence/exp06_calibrate_ext.toml BUDGET=150
make dispatch-calibration RUNS="results/exp06_calibrate/20260929-214423 results/exp06_calibrate/<new>" WRITE=1
```

**Cost.** The first batch cost $51.34 for 15 tasks (Haiku $17.41, Sonnet
$11.61, Opus $22.33). Without Haiku that is $33.94, about $2.26 per task
across two models. Forty tasks at that rate is about $90; stratum B's
longer briefs and 80-turn cap push its 12 tasks up, so plan on $100 to
$130 and set the budget at $150. The estimate step gives the list-price
figure before anything runs.

**Haiku is dropped (decided 2026-10-01).** The protocol calibrates on
three models. Haiku was a third of the first batch's spend, and the
Haiku-to-Sonnet question is answered twice now (a perfect, free trigger
costs 2.2× to 2.3× always-Sonnet). H0 needs only the Sonnet and Opus pass
rates. This is a recorded deviation from Section 7.1. If H0 passes, Haiku
may be run on the hard stratum alone before registration.

## Decision rule

H0 is evaluated on the **pooled** set (15 first-batch tasks plus the 40
new ones, 55 tasks). The bar is unchanged: at least 10 measured-hard tasks
(10% of 55 is below 10, so the absolute figure binds). Labels are measured
as in Section 7.1: hard means Opus passes at least 2 of 3 and Sonnet at
most 1 of 3.

This bar needs a 25% hard rate among the new tasks, because the first batch
contributes none. That is deliberate: a ladder with fewer than 10 hard tasks
in 55 has too little to earn for the confirmatory run to resolve a 10-point
gain. If the new tasks show headroom below that rate, the result is still
reported per stratum, so a stratum that does carry headroom (for example
long-horizon work) is visible for a later, separately scoped study.

**If H0 passes:**

1. Draw the 30/70 tuning and confirmatory split by group (Section 7.1).
2. Revise the ladder to v0.4 before registration: drop the forced check;
   gate the advisor on evidence (first verifier failure, a recurring error)
   instead of a standing instruction; keep `explore_handoff_clean` as the
   cheapest arm. Record these as the answers to Appendix C.
3. Fit K, N and the prompts on the tuning split. Register. Run the
   confirmatory ladder on the confirmatory split.
4. Only then does exp07 become worth registering, and only the parts of it
   that survive the exp06 idle-cost findings.

**If H0 fails:** it has failed twice. Per the stopping rule, the finding
"no frontier-only work found in long single-session coding tasks, harvested
handoffs, long-horizon and multi-repo tasks, ambiguous briefs and read-only
investigation" is the result. Write the final findings note, bump
`results.md` to v1.2 with the pooled Stage 0 table, close exp06, and
re-scope exp07 to the one question the idle-cost data left open: whether a
cheap external gate can suppress unjustified escalation requests.

## Reporting

A findings note `findings/<date>-exp06-stage0-ext.md` with: the pooled
calibration table, per-stratum pass rates and labels, Sonnet failures
inspected one by one (capability gap or grader strictness, as in the first
batch), the perfect-trigger reference values on the pooled set, the Haiku
decision, the authorship record, and the brief-statistics comparison.

## Deviations from v0.3 to record

| protocol | this run | why |
|---|---|---|
| Three models in calibration | Haiku dropped | question answered twice; a third of the spend |
| 40-turn cap | 80 for stratum B, 40 elsewhere; 40 reported as sensitivity | long-horizon tasks are meant to exceed one session |
| About 95 tasks before the split | 55 pooled | one extension, budget |
| Ambiguous stratum with a scripted user | stratum C calibrated on static arms only; the scripted user is built only if H0 passes | the user script is ladder-arm machinery |
