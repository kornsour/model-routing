# Route on evidence: what the escalation ladder costs when nothing needs escalating

*White paper. exp06 results, exploratory. Governing AI model spend.*

Results of running the exp06 protocol (`docs/experiments/exp06-route-on-evidence/paper.md`,
v0.3) on the current Claude models: a headroom gate, then five routing arms
on the same fifteen tasks, then the one task-set extension the protocol
allows (40 drawn tasks, headroom gate only). **exp06 is closed:** the gate
failed twice.

| 5 / 55 | 2.7× | $0.26 | 0.30× |
|---|---|---|---|
| tasks the frontier model could do and the mid-tier model could not, over two draws (the study needed 10) | cost per completed task of the full escalation ladder against plain Sonnet, for the same completion | average cost of one consultation of the frontier advisor, about what Sonnet charges to do the whole task | cost of Sonnet 5.5 and Opus 5.5 against their 5.0 predecessors on the same tasks |

Andrew Kaiserauer. 30 September 2026, revised 1 and 2 October 2026. **Version 1.2
(exploratory; not registered; exp06 closed).** Companion to "Route on evidence, not on the prompt" (exp06
hypothesis paper, v0.3) and "Cheapest per token is not cheapest per task"
(exp05, v1.0). Harness: github.com/kornsour/model-routing. Study id: **exp06**.

Evidence tags as in the companion papers: **MEASURED** in this study,
**VENDOR** self-reported, **UNTESTED** reasoned design.

## Summary

The hypothesis paper proposed a way to keep everyday AI work on a cheaper
model without blocking access to the frontier model: every session starts on
the mid-tier model, and escalates up a ladder only on evidence (a frontier
advisor it can consult, a forced advisor check before it finishes, and a
handoff to the frontier model when its own acceptance tests fail). Its study
protocol first asks whether there is any work the frontier model can do and
the mid-tier model cannot (the headroom gate, H0), because without such work
a ladder has nothing to earn.

We wrote fifteen long, specification-heavy coding tasks designed to find
that work and ran them three times each on Haiku 4.5, Sonnet 5.5 and Opus
5.5. **We found none.** Sonnet completed 44 of 45 attempts and Opus 45 of
45; the one Sonnet miss was an ambiguous sentence in our brief. The only
headroom was between Haiku and Sonnet, and even a perfect, free trigger
from Haiku to Sonnet would have cost 2.3 times always-Sonnet, because Haiku
spends most of its turn budget on the tasks it fails.

The protocol allows one extension, so we drew forty more tasks from the
sources most likely to hold frontier-only work: real handoffs from the
author's own sessions, long-horizon work across several packages, briefs
with a requirement left out, and read-only investigation. Sonnet completed
99 of 120 attempts and Opus 109 of 120. **Five of the pooled 55 tasks were
frontier-only, against a bar of ten,** and two of those five hang on a
grader or brief choice. A perfect, free Sonnet-to-Opus trigger would buy
about 8 points of completion for 14% more than plain Sonnet. The headroom
gate has failed twice, and by its own stopping rule the study ends there
(Section 3.2).

We then ran the ladder anyway, with the user's approval and labelled as
exploratory, to measure the one thing this task set can measure: **what the
ladder costs on work where it has nothing to earn.** That is most everyday
work, and the hypothesis paper required the ladder to cost no more than
1.5 times plain Sonnet there (L1, condition 2).

| arm | completion | cost per completed task | vs plain Sonnet |
|---|---:|---:|---:|
| plain Sonnet 5.5 (control) | 100% | $0.271 | 1.00× |
| Sonnet + handoff on failed self-tests | 98% | $0.279 | **1.00×** [0.93, 1.10] |
| Sonnet + advisor, no forced check | 98% | $0.518 | 1.85× [1.57, 2.16] |
| Sonnet + advisor + forced check | 100% | $0.670 | 2.42× [2.26, 2.60] |
| **full ladder** (all of the above) | 100% | $0.727 | **2.63×** [2.44, 2.84] |
| plain Opus 5.5 (ceiling) | 100% | $0.496 | 1.83× |

Ratios on the 14 measured-easy tasks, 95% task-clustered intervals.

The two rungs behave completely differently when nothing goes wrong:

- **The evidence-gated handoff is free when idle.** Asking Sonnet to write
  its own acceptance tests and handing off only if they fail cost the same as
  plain Sonnet and never fired. It passes the cost condition.
- **The advisor is not.** Every consultation re-reads the whole transcript at
  frontier prices, uncached, and costs about $0.26, as much as Sonnet charges
  to do the entire task. Sonnet consulted it voluntarily on 42% to 76% of
  tasks that did not need it, and the forced check added one more
  consultation on every session that had not. The full ladder cost 2.6 times
  plain Sonnet and **1.5 times plain Opus**, for identical completion. It
  fails both cost conditions.

**What to do with this.** For coding work like this, the companion study's
advice stands and is stronger one model generation later: make the
mid-tier model the default and stop. If a safety net is wanted, use the
cheap one: a handoff triggered by failing checks. Do not attach a
frontier advisor to every session, and do not force a consultation before
every finish; if an advisor rung is used at all, gate it on the same evidence
as the handoff. The ladder's ability to help on genuinely hard work was
never tested, because across two draws there was too little of it to test
on.

A side finding matters more for budgets than any routing rule: **on the same
tasks, Sonnet 5.5 and Opus 5.5 cost about 30% of what Sonnet 5 and Opus 5
cost**, mostly because they finish in fewer turns.

## 1. What was tested

The hypothesis paper (v0.3) states the ladder's claims against the right
control, the best fixed default (always-mid-tier), rather than the most
expensive model:

- **H0 (gate).** At least 10 tasks (or 10% of the set) are *measured hard*:
  the frontier model passes at least 2 of 3 trials and the mid-tier model at
  most 1 of 3.
- **L1.** The ladder (1) completes at least 10 points more hard tasks than
  always-mid-tier, (2) costs at most 1.5× always-mid-tier per completed task
  on easy tasks, and (3) costs less than always-frontier over the whole set.
- **L2.** The advisor rung does most of the work, and escalations land on
  tasks that need them (recall at least 70%, precision at least 50%).
- **L6.** The handoff trigger carries information: it beats a random handoff
  at the same rate.

H0 is a stopping rule: if it fails after one extension of the task set, the
study reports that and does not run the ladder. This run is the first
batch. Because the user approved the ladder arms before the gate was
known, and because their cost on no-headroom work is itself a question the
hypothesis paper raised (Appendix C: "one forced advisor call may cost more
than a short Sonnet session"), we ran them and label every result here as
exploratory.

## 2. What was run

**Tasks.** Fifteen tasks written for this study before any model was run on
them, in two new stdlib-only Python fixture repositories, each with a
reference solution and hidden tests (the untouched repository fails them and
the reference solution passes; both are checked by the harness). The tasks
were built to be hard in the ways a mid-tier model is expected to slip:

- **`toolbelt`, 8 tasks: implement or repair a module to a written
  specification.** npm semver ranges, RFC 6902 JSON Patch and RFC 6901
  pointers, Vixie cron with day-of-month/day-of-week rules and daylight
  saving, glob matching with globstar, braces and dotfiles (with an
  adversarial-pattern performance test), applying unified diffs with offset
  search, ISO 8601 durations with calendar arithmetic across DST, INI
  inheritance and interpolation, and exact money allocation and formatting.
- **`orchestra`, 7 tasks: change a deterministic job scheduler whose run
  loop is specified in its docstring.** Add trigger rules, fix three
  interacting retry bugs and add timeouts and jitter, migrate a storage
  format across three versions with a checksum, make the loop scale to
  20,000 jobs without changing a single scheduling decision, add
  cancellation, add reservation and priority aging, and add critical-path
  planning with an exact output format.

Briefs have a median of about 780 tokens (430 to 1,030), between the real
task chips (about 500) and subagent dispatches (about 1,100) harvested from
the author's own transcripts. Hidden tests are deterministic; there is no
LLM judge.

**Models.** Claude Haiku 4.5, Sonnet 5.5 and Opus 5.5, pinned by exact id,
through Claude Code 2.1.285 in headless mode on the author's subscription
login, priced at API list prices from the harness's table (the CLI's own
cost report matched it on every session). A first calibration on Sonnet 5 /
Opus 5 was stopped after 14 cells when the study moved to the current models
(Section 5).

**Runs.** All sequential, randomized block order, 40-turn cap per session,
3 trials.

| run | cells | spend | what |
|---|---:|---:|---|
| `exp06_calibrate/20260929-214423` | 135 | $51.34 | Stage 0: every task on Haiku, Sonnet, Opus |
| `exp06_ladder/20260930-044605` | 225 | $110.14 | five arms on every task, fresh |
| smoke runs and aborted 5.0 calibration | 25 | $24.50 | not analysed except Section 5 |
| **total** | | **$185.97** | budget $500 |

No run hit a usage limit, a provider outage or its budget.

**Arms in the ladder run** (Sonnet 5.5 is the working model everywhere;
Opus 5.5 is the advisor and the handoff target):

| arm | what it adds to a plain Sonnet session |
|---|---|
| `static_sonnet` | nothing (primary control, run fresh) |
| `explore_handoff_clean` | Sonnet first writes acceptance tests for the brief in `.verifier/`; after it finishes, the harness runs the visible tests, those tests and a scope check; on failure Sonnet is resumed once with the failure, and a second failure hands the task to Opus in a clean checkout with the failure log |
| `sonnet_advisor` | Claude Code's advisor tool with Opus 5.5, prompted to consult it before committing to an approach, on recurring errors and before finishing; if the session never consulted it, the harness resumes the session once and requires a consultation (the forced check) |
| `ladder_noforce` | the advisor, the self-written acceptance tests and verifier loop, the handoff, and an `ESCALATE:` line the model can use to ask for Opus |
| `ladder` | all of `ladder_noforce` plus the forced check |

`static_opus` and `static_haiku` come from the calibration run. The
hypothesis paper's other arms were not run (Appendix C lists every
deviation).

## 3. Stage 0: is there frontier-only work?

### 3.1 The first batch: 15 written tasks

| model | passed | cost per completed task [95% CI] | median turns | sessions at the 40-turn cap |
|---|---:|---:|---:|---:|
| Haiku 4.5 | 12/45 (27%) | $1.45 [$0.82, $3.92] | 38 | 21 |
| Sonnet 5.5 | 44/45 (98%) | $0.264 [$0.233, $0.297] | 9 | 0 |
| Opus 5.5 | 45/45 (100%) | $0.496 [$0.448, $0.545] | 8 | 0 |

**MEASURED** Measured labels: 14 easy, 1 medium, **0 hard**. H0 required 10.
Opus never passed a task that Sonnet failed.

Sonnet's single failure (`tb-cron-03`, one trial of three) returned a
generator from `iter_fires` where the hidden tests compare against a list;
the brief said "returning the next `count` fire times in order". It is a
strict grader meeting an ambiguous sentence, not a capability gap, and it
recurred once in the ladder run in the same form.

The tasks were not easy in absolute terms. Haiku 4.5 passed 27% of them and
ran into the turn cap on 21 of 45 attempts. The headroom that exists is
between Haiku and Sonnet, and it does not pay: charging Haiku's attempt plus
a Sonnet rerun exactly when Haiku failed (a perfect, free trigger) gives
**$0.596 per completed task, 2.3× always-Sonnet**, at the same completion.
exp05 found the same, 2.2× ($0.221 against $0.099), on Sonnet 5 and a
different task set.

After the first batch H0 had failed once, which triggered the one allowed
extension (3.2). On the first batch alone the perfect-trigger reference
values are trivial: with no hard tasks, a perfect Sonnet-to-Opus trigger never fires and costs
exactly what plain Sonnet costs.

### 3.2 The extension: 40 drawn tasks, and the pooled 55

The one extension (`extension-plan.md`) changed the task source and shape,
not the bar. Forty new tasks in four strata, built, validated and frozen
before any model saw them (`findings/2026-10-01-exp06-stage0-ext-taskset.md`),
run on Sonnet 5.5 and Opus 5.5 at 3 trials, 80 turns for the long-horizon
stratum and 40 elsewhere. Haiku was dropped (Appendix C). 240 cells cost
$88.48 at list price. Full note: `findings/2026-10-02-exp06-stage0-ext.md`.

| stratum | tasks | Sonnet passed | Opus passed | Sonnet $/completed | Opus $/completed | easy | medium | hard | unsolved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| first batch (3.1) | 15 | 44/45 | 45/45 | $0.264 | $0.496 | 14 | 1 | 0 | 0 |
| A. harvested real handoffs | 16 | 40/48 | 41/48 | $0.282 | $0.552 | 12 | 1 | 1 | 2 |
| B. long-horizon, multi-package | 12 | 29/36 | 34/36 | $0.496 | $0.827 | 9 | 0 | 3 | 0 |
| C. ambiguous brief | 6 | 12/18 | 16/18 | $0.199 | $0.281 | 4 | 0 | 1 | 1 |
| D. read-only investigation | 6 | 18/18 | 18/18 | $0.100 | $0.188 | 6 | 0 | 0 | 0 |
| **pooled** | **55** | **143/165** | **154/165** | | | **45** | **2** | **5** | **3** |

**MEASURED** Labels by the protocol's rule (hard: Opus at least 2 of 3,
Sonnet at most 1 of 3). **5 hard against a bar of 10: H0 is not met, for
the second time.** Counting every unsolved task as hard would give 8.

The five hard tasks, each failure read against its grade detail:

- **Clean capability gaps (2).** On an ambiguous brief, Sonnet invented its
  own JSON format three times where the repo's docs pointed at the existing
  one; on a long-horizon task it fixed the symptom (month bucketing) and
  left the stored timestamps outside the store's UTC contract, three times.
- **A soft judgement gap (1).** On a claims audit, each failed Sonnet trial
  got one different verdict wrong.
- **Borderline grader or brief (2).** On one, every failed cell, Opus's
  included, raised `KeyError` where the test wanted `ValueError`; on the
  other the brief did not say which function owned a default path.

So the frontier-only work in 55 tasks is between 2 and 5 tasks. It
concentrates in long-horizon work (3 of 12), the only stratum near the 25%
rate the extension needed; real handoffs gave 1 of 16 and read-only
investigation none. Raising the long-horizon cap to 80 turns changed
nothing: one Sonnet session of 72 went past 40 turns, and it failed.

Four tasks had a defective test that rejected a defensible reading; 16
cells that failed only that test were re-graded as passes, with the
originals kept (Appendix C). Before re-grading the extension stood at 91
and 101 of 120. No correction made a grade stricter, and the hard set is
the same five tasks before and after re-grading.

Reference values on the 52 tasks that are not unsolved (95% task-clustered
intervals):

| arm | completion | cost per completed task | vs plain Sonnet |
|---|---:|---:|---:|
| plain Sonnet 5.5 | 91% [84, 97] | $0.277 [$0.236, $0.324] | 1.00× |
| plain Opus 5.5 | 98% [96, 100] | $0.497 [$0.430, $0.568] | 1.79× |
| perfect Sonnet-to-Opus trigger, free | 99% [97, 100] | $0.317 [$0.250, $0.395] | 1.14× |

That is the ceiling for any escalation ladder on this work: 8 points of
completion for 14% more cost, with an oracle trigger. The measured ladder's
idle cost alone (Section 4) is 1.85× to 2.63× plain Sonnet for every arm
with an advisor, so no advisor-based ladder could have reached that ceiling
here; the handoff-only arm, idle at 1.00×, is the only rung that could.

## 4. What the ladder costs when nothing needs escalating

### 4.1 Completion and cost

| arm | completion [95% CI] | cost per completed task [95% CI] | median wall time per task | advisor consultations | handoffs |
|---|---:|---:|---:|---:|---:|
| `static_sonnet` | 100% [100, 100] | $0.271 [$0.242, $0.300] | 73 s | 0 | 0 |
| `explore_handoff_clean` | 98% [93, 100] | $0.279 [$0.261, $0.299] | 69 s | 0 | 0 |
| `ladder_noforce` | 98% [93, 100] | $0.518 [$0.438, $0.602] | 119 s | 35 | 0 |
| `sonnet_advisor` | 100% [100, 100] | $0.670 [$0.614, $0.731] | 154 s | 61 | 0 |
| `ladder` | 100% [100, 100] | $0.727 [$0.670, $0.792] | 185 s | 57 | 0 |
| `static_opus` (calibration) | 100% [100, 100] | $0.496 [$0.448, $0.545] | 104 s | 0 | 0 |

**MEASURED** 45 cells per arm (15 tasks × 3 trials). No session in any arm
hit the turn cap, so the capped-cells sensitivity analysis changes nothing.
No arm handed off: every verifier check passed, no session asked to
escalate, and none stalled.

### 4.2 The L1 conditions

| arm | c1: hard stratum, completion vs Sonnet | c2: easy stratum, cost / Sonnet (bound 1.5) | c3: whole set, cost / Opus (bound 1.0) | L1 |
|---|---|---|---|---|
| `explore_handoff_clean` | no hard tasks | **1.00** [0.93, 1.10] supported | **0.56** [0.52, 0.60] supported | inconclusive |
| `ladder_noforce` | no hard tasks | 1.85 [1.57, 2.16] not supported | 1.04 [0.87, 1.24] inconclusive | not supported |
| `sonnet_advisor` | no hard tasks | 2.42 [2.26, 2.60] not supported | 1.35 [1.25, 1.46] not supported | not supported |
| `ladder` | no hard tasks | **2.63** [2.44, 2.84] not supported | **1.47** [1.34, 1.59] not supported | **not supported** |

Condition 1 cannot be evaluated without hard tasks. The full ladder fails
the other two outright: on this work it costs 2.6 times the best fixed
default and half as much again as simply using the frontier model. The
explore-then-handoff arm meets both cost conditions and is inconclusive only
because it had nothing to prove on condition 1.

### 4.3 Where the ladder's cost comes from

**The advisor is half the bill.** **MEASURED** Opus's advisor tokens were
50% of the full ladder's spend and 49% of `sonnet_advisor`'s. Across all
arms, one advisor consultation cost **$0.259** on average (153
consultations). That is the size of a whole plain-Sonnet task ($0.271). The
advisor tool reads the full transcript each time at the frontier model's
input price, with no caching (**VENDOR**, Claude Code documentation; our
token counts agree). A consultation late in a session, which is when the
"before you finish" instruction puts it, is the most expensive kind.

**The forced check is the second half.** In the full ladder, 26 of 45
sessions finished without consulting the advisor, so the harness resumed
them to require a consultation. Each forced check cost $0.458 on average,
$0.37 of it advisor tokens. All 26 of those cells passed; we cannot see what
each would have done without the check, but the arm without it
(`ladder_noforce`) completed 44 of 45, and its one miss was the ambiguous
`iter_fires` sentence, not a gap an advisor would close. Removing the forced
check cut the ladder's cost per completed task from $0.727 to $0.518.

**Sonnet asks for advice it does not need, and how often depends on the
prompt.** With only the advisor instruction (`sonnet_advisor`), Sonnet
consulted voluntarily on 34 of 45 tasks (76%). With the acceptance-test
instruction added (`ladder`, `ladder_noforce`), it consulted on 19 and 27 of
45 (42% and 60%). No task needed help, so every one of these consultations
was, in the protocol's terms, a false escalation: precision 0% against a
base rate of 0%. This is the opposite of the risk the hypothesis paper named
first ("models may not escalate when they should"): on easy work, the
working model over-consults.

**The handoff rung costs nothing until it fires.** Writing acceptance tests
first and running them after cost a few cents per task at most: the
explore arm's cost per completed task was within 3% of plain Sonnet's
(interval 0.93 to 1.10). It never fired, because Sonnet passed its own tests
every time.

### 4.4 The verifier

The deployable verifier (scope check, visible tests, and the tests the
working model wrote for the brief) ran on 135 cells across the three arms
that used it. It rejected one attempt (in `explore_handoff_clean`; Sonnet
fixed it on the resume), accepted every cell in the end, and let **one false
accept** through in each of two arms (`explore_handoff_clean`,
`ladder_noforce`): 2 of 135 accepted cells failed the hidden tests. One was the ambiguous `iter_fires` return type
above; the other was a real miss (Sonnet did not reject fractional years and
months in duration arithmetic, a clause in the brief its own tests did not
cover). Self-written tests share the working model's blind spots, as the
hypothesis paper warned, but at a 2% false-accept rate on this set they
were not the ladder's problem.

### 4.5 What could not be measured

With no hard tasks, the parts of the design that matter most were never
exercised on the main set: whether the working model recognises when it is
out of its depth (recall), whether a handoff from a clean checkout beats one
that inherits the failed attempt (L4), whether the trigger beats random
handoffs at the same rate (L6: the explore arm's handoff rate was 0%, so the
random-matched baseline is plain Sonnet), and whether the advisor rescues
hard tasks (L2). The handoff path itself works end to end on real models: in
a smoke run with Haiku as the working model and Sonnet as the target, Haiku
hit the turn cap, the no-progress trigger fired, and Sonnet completed the task
from a clean checkout ($0.74 for the cell).

## 5. Side finding: the model generation moved cost more than any routing rule

Stage 0 was first started on Sonnet 5 and Opus 5 (what the `sonnet` and
`opus` aliases meant in the installed Claude Code) and stopped after 14
cells when the user moved the study to the current models. All 14 passed.
**MEASURED** On the seven tasks both generations ran:

| | Sonnet 5 → Sonnet 5.5 | Opus 5 → Opus 5.5 |
|---|---:|---:|
| cost | $6.20 → $1.83 (**0.30×**) | $12.61 → $3.77 (**0.30×**) |
| turns | 198 → 84 | 215 → 80 |
| output tokens | 241k → 72k | 185k → 87k |
| prompt tokens | 10.3M → 2.3M | 9.3M → 2.4M |

Sums of per-task means; one 5.0 trial against three 5.5 trials per task, so
this is indicative rather than a controlled comparison. The Claude Code
version also changed (2.1.278 → 2.1.285), so the saving belongs to model and
harness together. Opus 5.5's list price is 20% lower than Opus 5's and Sonnet
5.5's is unchanged, so most of the saving comes from finishing in fewer
turns, which means re-reading a growing context fewer times.

For a budget owner this is the largest number in the study. Moving to the
current generation cut cost per task by about 70% at the same completion.
The best routing rule we measured saved nothing, and the ladder added 160%.

## 6. What this means

For the governance question the hypothesis paper started from (keeping
everyday AI work on cheaper models without blocking the frontier model),
this study adds four things.

1. **Default to the mid-tier model; for this class of work that is the whole
   answer.** On long, specification-heavy coding tasks that were built to
   separate the models, Sonnet 5.5 matched Opus 5.5 on every task at 55% of
   the cost. This repeats exp05's result on the previous generation and a
   harder task set. The saving comes from the default and from staying
   current, not from a router.
2. **A safety net can be nearly free if it is gated on evidence.** Having the
   working model write acceptance tests and escalating only when they fail
   added no measurable cost when nothing failed (1.00× plain Sonnet, interval
   0.93 to 1.10). It is the one rung of the
   ladder safe to switch on by default. Whether it escalates when it should
   is untested here.
3. **Do not put a frontier advisor on every session, and do not force a
   consultation before every finish.** On work that does not need it, the
   advisor doubled the cost of a session per consultation, the working model
   consulted it on most tasks anyway, and the forced check added one more
   consultation to more than half the sessions. The result cost more than
   running the frontier model outright. If an advisor rung is used, it
   should be triggered by the same evidence as the handoff (a failing check,
   a recurring error), not by a standing instruction. That is a change to the
   ladder's design, not only its parameters. With exp06 closed it is
   recorded as the answer to the hypothesis paper's Appendix C question on
   the forced check, not carried into a v0.4.
4. **Before building routing, move to the current models.** The generation
   change cut cost by about 70% with no routing at all.

What this does not show is that escalation never pays. It shows that in
55 tasks built or drawn for the purpose, the current mid-tier model failed
where the frontier model succeeded on at most five, so a perfect trigger is
worth about 8 points of completion for 14% more cost, and that the ladder as specified is
expensive when it has nothing to do. Anyone deploying it should expect most
of their traffic to look like this study's, and price the idle cost first.

## 7. What was answered and what was not

The runs settled the questions that depend on easy work and the headroom
question itself. Every question that depends on hard work stays open, and
by the stopping rule it stays open in this study: two draws found too
little hard work to test it on.

| hypothesis | status | what the run showed |
|---|---|---|
| **H0** headroom exists | **not met, twice: exp06 closed** | 0 of 15 in the first batch; 5 of 55 pooled after the one allowed extension, against a bar of 10 (Section 3.2). The finding stands for this class of work. |
| **L1 c1** ladder helps on hard tasks | **not testable here** | 5 hard tasks; a perfect free trigger is the ceiling, 1.14× plain Sonnet for 8 points of completion |
| **L1 c2** ladder costs at most 1.5× plain Sonnet on easy tasks | **answered: not supported** for every arm with an advisor (1.85× to 2.63×); **supported** for the handoff-only arm (1.00×) |
| **L1 c3** ladder costs less than plain Opus over the set | **answered: not supported** for the full ladder (1.47×) and the advisor arm (1.35×); **supported** for the handoff-only arm (0.56×) |
| **L2** advisor rung does most of the work, escalations land where needed | **half answered** | precision measured at 0% on easy work (every consultation unnecessary); recall open, needs hard tasks |
| **L3** evidence beats a prompt classifier on cost | **open** | `C2_trained` not run (no tuning split) |
| **L4** clean checkout beats carrying the failed attempt | **open** | no handoff fired |
| **L5** clarifying reduces handoffs | **open** | ambiguous stratum built and calibrated on static arms (1 hard of 6); the scripted user was never run |
| **L6** the trigger carries information | **open** | handoff rate 0%, so the random-matched baseline equals plain Sonnet |
| Appendix C: forced check vs the 1.5× bound | **answered** | the forced check alone adds about $0.46 per session; it cannot coexist with the bound. Drop the check. |
| Side finding: generation change | **measured** | about 0.30× cost per task from 5.0 to 5.5, same completion |

Two things the design did not cloud: the idle-cost numbers are measured on
the stratum they apply to, with tight task-clustered intervals, and would not
change under any other task set. One thing it still does: every fixture and
hidden test, in both draws, was written by the model family under test
(Section 8). The extension removed the other first-batch caveat, that the
strata most likely to carry headroom were never built.

## 8. Threats to validity

- **Exploratory, not registered.** Parameters (K = 2, the prompts, the
  forced-check rule) were chosen before the run but not on a tuning split,
  and the decision rules were applied after the fact. The results are
  descriptive.
- **Too little headroom, so no test of the ladder's benefit.** Everything
  in Section 4 is about idle cost. Condition 1 of L1, L2's recall, L4 and L6
  remain open, and with 5 hard tasks of 55 they cannot be resolved here.
- **Single author, and the author's assistant wrote the tasks.** The tasks
  and reference solutions were written by an Opus-class model working for the
  author, the same model family that was tested. Tasks written by the tested
  model family may sit inside what it finds natural. The real-handoff source
  the protocol prefers (the author's own harvested chips) was not used,
  because turning them into deterministically graded fixtures was out of
  scope for this batch; building tasks on third-party open-source libraries
  was attempted and not pursued, because running downloaded code was blocked
  in this environment. The extension used 16 real handoffs, but their
  fixtures, hidden tests and reference solutions, and every task in the
  other three strata, were again written by Claude Opus 5.5; the planned
  cross-family re-derivation was not done.
- **Filtered real handoffs.** 26 of the 42 handoffs drawn were skipped
  because no offline deterministic grader could be written or the content
  was private. Work that needs the network, a UI or a live service, plausibly
  where headroom lives, is under-represented.
- **Graders corrected after the run.** Four tests rejected a defensible
  reading and were widened after the extension ran; 16 cells were re-graded
  (Appendix C). The hard set did not change. Two of the five hard tasks still
  hang on a grader or brief choice.
- **Fifty-five tasks, fifteen in the first batch.** The intervals are
  task-clustered and honest about it, but a set this small can miss a class
  of hard work entirely. Long-horizon work (3 hard of 12) is the stratum a
  larger study should draw from.
- **Grader strictness.** Both Sonnet misses in Stage 0 and one of the two
  verifier false accepts involve the same ambiguous sentence in one brief.
  Strict graders on ambiguous briefs understate the mid-tier model slightly;
  they do not create headroom.
- **Static arms from two runs.** Plain Sonnet was re-run fresh in the ladder
  run; plain Opus and Haiku come from the calibration run, which ended 1.5
  hours before the ladder run started, on the same login. The two Sonnet runs agree ($0.271 and $0.264 per
  completed task).
- **One vendor, one harness, list prices.** Claude Code's advisor tool,
  headless mode and prompt caching shape these costs. A gateway-based
  advisor that caches the transcript, or a different agent harness, could
  change the advisor's price materially.
- **Model and harness drift.** The Claude Code version changed between the
  aborted and the completed calibration, and the aliases resolve to newer
  models over time; exact model ids are pinned and recorded for every
  session.

## 9. Next steps

exp06 is closed. The ladder is not revised to v0.4, not registered, and the
confirmatory run does not happen; the protocol's answer for this class of
work is that there is too little frontier-only work for an escalation ladder
to earn its idle cost.

1. **Two follow-ups take the question the idle-cost data left open:** the
   advisor consultations on easy work, about $0.26 each, made on 42% to 76%
   of tasks. exp07 tests whether allowing consultation only on evidence
   removes them (`../exp07-evidence-prompt/preregistration.md`); exp08
   tests a Jev gate on the requests (`../exp08-jev-gate/preregistration.md`).
   Neither needs a hard stratum.
2. **Use the evidence-gated handoff as the default safety net** where one is
   wanted. It is the only rung that was free when idle.
3. **Re-state L1 condition 2 as the deployment test it turned out to be.**
   The idle cost of every rung, measured on easy work, should be a gate
   before any claim about hard work is tested.
4. **If headroom is studied again, start from long-horizon work.** It was
   the only stratum near the rate a ladder study needs, and a separate study
   should draw it at scale and have a different model family write the
   graders.
5. **Keep measuring generations.** Re-run Stage 0 whenever the default
   models change; the cost of a task moved more between two model releases
   than between any two policies in this study.

## Appendix A. Stage 0 per task

| task | Haiku 4.5 | Sonnet 5.5 | Opus 5.5 | Sonnet mean cost | Opus mean cost | label |
|---|---:|---:|---:|---:|---:|---|
| or-cancel-05 | 0/3 | 3/3 | 3/3 | $0.324 | $0.557 | easy |
| or-perf-04 | 0/3 | 3/3 | 3/3 | $0.349 | $0.654 | easy |
| or-plan-07 | 0/3 | 3/3 | 3/3 | $0.266 | $0.487 | easy |
| or-retries-02 | 1/3 | 3/3 | 3/3 | $0.307 | $0.665 | easy |
| or-starve-06 | 3/3 | 3/3 | 3/3 | $0.178 | $0.559 | easy |
| or-store-03 | 0/3 | 3/3 | 3/3 | $0.227 | $0.375 | easy |
| or-triggers-01 | 3/3 | 3/3 | 3/3 | $0.183 | $0.471 | easy |
| tb-cron-03 | 0/3 | 2/3 | 3/3 | $0.165 | $0.405 | medium |
| tb-duration-06 | 0/3 | 3/3 | 3/3 | $0.207 | $0.449 | easy |
| tb-glob-04 | 1/3 | 3/3 | 3/3 | $0.379 | $0.544 | easy |
| tb-ini-07 | 1/3 | 3/3 | 3/3 | $0.257 | $0.467 | easy |
| tb-jsonpatch-02 | 2/3 | 3/3 | 3/3 | $0.246 | $0.468 | easy |
| tb-money-08 | 1/3 | 3/3 | 3/3 | $0.193 | $0.329 | easy |
| tb-patch-05 | 0/3 | 3/3 | 3/3 | $0.232 | $0.396 | easy |
| tb-semver-01 | 0/3 | 3/3 | 3/3 | $0.357 | $0.616 | easy |

## Appendix B. Reproducing

Task set `tasks/exp06/` (hash `e2f1de4a3ba9…`, commit `82c0230`; rebuild
`tasks.jsonl` from `tasks/exp06/briefs/` with `uv run python
tasks/exp06/build_tasks.py`, validate with the harness validator). Configs
in `experiments/exp06-route-on-evidence/exp06_*.toml`. Harness commits: ladder policy and
advisor pricing `7c6156b`, analysis `9420739`, model pins `d30a822`, budget
pauses `c40a1b6`.

```bash
make dispatch-run EXP=experiments/exp06-route-on-evidence/exp06_calibrate.toml BUDGET=260
make dispatch-run EXP=experiments/exp06-route-on-evidence/exp06_ladder.toml BUDGET=250
uv run python -m model_routing.dispatch.exp06 \
    --calibration results/exp06_calibrate/<stamp> \
    --ladder results/exp06_ladder/<stamp> --out exp06_analysis.md
```

Extension: task set `tasks/exp06/tasks_ext.jsonl` (40 tasks; build with the
same script, validate with `scripts/validate_agentic_tasks.py`), config
`exp06_calibrate_ext.toml`, Claude Code 2.1.285, seed 20261001.

```bash
make dispatch-run EXP=experiments/exp06-route-on-evidence/exp06_calibrate_ext.toml BUDGET=150
uv run python -m model_routing.dispatch.exp06 \
    --calibration results/exp06_calibrate/<first stamp> results/exp06_calibrate_ext/<stamp> \
    --out exp06_pooled_analysis.md
```

Run directories are git-ignored and backed up (`make backup`); the Stage 0
notes are `findings/2026-09-30-exp06-stage0.md`,
`findings/2026-10-01-exp06-stage0-ext-taskset.md` and
`findings/2026-10-02-exp06-stage0-ext.md`.

## Appendix C. Deviations from the v0.3 protocol

| protocol (v0.3) | this run | effect |
|---|---|---|
| Register before the confirmatory run; Appendix C decisions signed off | Not registered; Appendix C still open | Every result is exploratory |
| H0 is a stopping rule | Ladder arms run after H0 failed, with the user's approval | Measures idle cost only; says nothing about hard work |
| Sources: real handoffs first, then long coupled work, an ambiguous stratum, a non-coding stratum | Long coupled work only (15 author-written tasks) | No ambiguous stratum, so no L0 / L5 |
| About 95 tasks before the split; grouped 30/70 tuning/confirmatory split | 15 tasks, no split; parameters chosen a priori | Nothing tuned on the tested tasks; nothing held out either |
| Calibration on Haiku, Sonnet, Opus at 3 trials | Done (after a stopped first attempt on the 5.0 models) | None |
| Every arm run fresh in the confirmatory run | `static_sonnet` fresh; `static_opus`, `static_haiku` from calibration | Small; the two Sonnet runs agree |
| Arms `sonnet_effort`, `ladder_noL0`, `C2_trained`, `ladder_ideal`, `explore_handoff_carry` | Not run | Effort cannot change mid-session in headless mode; no ambiguous stratum; no tuning split to train on; with no handoffs, `ideal` and `carry` would equal their counterparts |
| Handoff after N turns without progress | The 40-turn cap stands in for N | Never triggered in the ladder run |
| Forced advisor check "before the model declares done" | Harness resumes the session once if it made no advisor call at all | A session that consulted early but not at the end was not forced; the forced check still ran on 26/45 ladder cells |
| Extension: three models in calibration | Sonnet and Opus only; Haiku dropped | Haiku-to-Sonnet answered twice; H0 needs only Sonnet and Opus |
| Extension: 40-turn cap | 80 for the long-horizon stratum, 40 elsewhere | None: one session of 72 went past 40, and it failed |
| Extension: reference solutions re-derived by another model family | Not done; every fixture and test written by Claude Opus 5.5 | Same-family authorship threat stands (Section 8) |
| Ambiguous stratum with a scripted user | Static arms only; no scripted user | L5 untested |
| Graders frozen before the run | Four tests widened after the run to accept a defensible reading; 16 cells re-graded, originals kept | Pass counts up 8 per model; hard set unchanged |
| One hour between paid runs | Kept between calibration, smoke and ladder runs; calibration itself was stopped and resumed once at a cell boundary to take a harness change (budget pauses) | None on outcomes |

## Appendix D. Version history

**v1.2 (2 October 2026).** Added the Stage 0 extension (Section 3.2): 40
drawn tasks, 5 of 55 hard pooled, H0 not met twice, exp06 closed. Updated the
summary, ledger, threats, next steps and appendices. Section 4 numbers
unchanged.

**v1.1 (1 October 2026).** Added Section 7, the ledger of answered and open
hypotheses, and pointed the next steps at `extension-plan.md`. No numbers
changed.

**v1.0 (30 September 2026).** First results.
