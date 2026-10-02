# Pre-registration: exp07, a gate on unjustified escalation

Status: **draft, not yet registered; re-scoped 2026-10-02.** Every run is
exploratory until the gates in "Before registering" are met.

## Why this was re-scoped

The first draft of exp07 tested Jev, a third-party decision model, as the
verifier that triggers a handoff and as a prompt-only router inside the
exp06 ladder. It ran only if exp06 found headroom. exp06 did not: 0 of 15
tasks were frontier-only, then 5 of 55 after the one allowed extension,
against a bar of 10, so exp06 closed (`../exp06-route-on-evidence/results.md`,
v1.2). A verifier or router that decides **when to hand off** has nothing to
earn on that work, and that question is dropped.

exp06 left one question open that does not need hard work, because the
cost it targets happens on easy work. With a frontier advisor available,
Sonnet 5.5 consulted it on **42% to 76% of tasks that did not need it**
(precision 0%), and each consultation cost about **$0.26**, roughly what
Sonnet charges to do the whole task. That is most of why every
advisor-based arm cost 1.85× to 2.63× plain Sonnet when idle. The
evidence-gated handoff, by contrast, was free when idle (1.00×). exp07 asks
whether a cheap gate between the working model and the advisor removes that
idle cost.

exp07 is a separate experiment with its own registration. No registered
field of exp05 or exp06 changes because of it, and no exp07 result changes
an exp06 verdict.

## Question

When the working model asks to consult a frontier advisor, can a cheap
external gate (Jev, or a small verifier model asking the same questions)
refuse the unjustified requests, and so bring an advisor-equipped session's
cost per completed task close to plain Sonnet's, without lowering
completion?

## Shared protocol

exp07 reuses the exp06 protocol (`../exp06-route-on-evidence/paper.md`,
v0.3) wherever this document is silent: the control, calibration-measured
difficulty labels, 3 trials, the paired randomized block design, the
40-turn cap (80 for long-horizon tasks, as in the exp06 extension), the
per-task majority oracle, intention to treat with outages redone, analyst
blinding, one run at a time, and the budget priority rule. It drops exp06's
H0 gate and its tuning and confirmatory split: the gate has no parameters
fitted to tasks (below).

## Task set

The pooled exp06 set, frozen at its current hash: `tasks/exp06/tasks.jsonl`
(15) and `tasks/exp06/tasks_ext.jsonl` (40), excluding the 3 unsolved
tasks: **52 tasks**, 45 measured easy, 2 medium, 5 hard. Mostly easy work is
the regime the question is about. The hard stratum is too small for a
verdict and is reported descriptively.

## Arms

| Arm | What happens | Role |
| --- | --- | --- |
| `static_sonnet` | Sonnet 5.5, no advisor, no handoff | control; run fresh |
| `ladder_noforce` | as in exp06: Sonnet 5.5 with the Opus 5.5 advisor and the evidence-gated handoff, no forced check | ungated comparator; run fresh |
| `ladder_gate_haiku` | as `ladder_noforce`, but every advisor request first goes to a Haiku 4.5 gate; if the gate says the request is not justified, the advisor call is refused and the worker continues alone | gated arm |
| `ladder_gate_jev` | the same, with `jev-1.13.0` answering the same questions | gated arm |

`static_opus` is taken from the exp06 calibration runs for reference and
not re-run.

**Gate input.** The brief, the worker's stated reason for the request (the
advisor tool's question text), the current diff (24,000 characters), and
the last 4,000 characters of worker output and visible test output.

**Gate questions.** Two, answered yes or no with a short reason: (1) Has
the worker hit evidence it cannot resolve alone: a failing check it has
already tried to fix, a recurring error, or a requirement the brief and the
repo do not settle? (2) Is the question one the brief or the repo already
answers? The request passes if (1) is yes and (2) is no. The two questions
and their wording are frozen at registration; nothing is fitted to tasks.

**Gate failures.** An HTTP error, timeout, invalid response or rate limit
**passes** the request: a gate that fails closed would turn outages into
blocked escalations. The gate error rate is reported.

**Mechanism (untested engineering).** The advisor is Claude Code's built-in
advisor tool, in the same session and cache. The proposed gate is a
`PreToolUse` hook on that tool that calls the gate and denies the call with
the gate's reason. Whether a hook can intercept the advisor tool in headless
mode is not yet known; it is the first gate in "Before registering". If it
cannot, the fallback is an MCP `request_advisor` tool that the harness gates
and then answers with an Opus call on the transcript. That changes the
advisor's caching and therefore its price, so it would be recorded as a
deviation and the ungated comparator would use the same tool.

## Hypotheses

Primary:

**G1 (a gate removes most of the idle cost).** On the 45 easy tasks, the
gated arm's cost per completed task, gate calls included, is at most 1.25×
`static_sonnet`, with completion non-inferior to `ladder_noforce` within 5
points. exp06 measured `ladder_noforce` at 1.85× [1.57, 2.16] idle.

Secondary, Holm-adjusted as one family:

| # | Hypothesis | Comparison |
| --- | --- | --- |
| G2 | The gate refuses at least half of the advisor requests made on easy tasks. | gated arm vs `ladder_noforce`, requests per session |
| G3 | Over all 52 tasks the gated arm costs less per completed task than the ungated one, at completion within 5 points. | gated arm vs `ladder_noforce` |
| G4 | The Jev gate and the Haiku gate differ in refusal rate on easy tasks by less than 10 points. | `ladder_gate_jev` vs `ladder_gate_haiku` |

G1 to G3 are tested for each gated arm; the Holm family covers all of
them. What would refute G1: an upper interval bound above 1.25×, or
completion more than 5 points below the ungated arm.

**Break-even, stated before any run.** Each refused request saves about
$0.26 and each gate call costs `c`. A gate that refuses a fraction `r` of
requests saves money only if `c < 0.26 × r`. At the expected Haiku gate
cost of about $0.01 to $0.03 per call, the gate pays once it refuses about
10% of requests. The Jev price row decides its break-even.

**Descriptive, no verdict.** On the 5 hard tasks: requests made, requests
refused, and completion per arm, listed per cell. A gate that refuses a
consultation on a cell that then fails, where the ungated arm passed the
same task, is reported by name as a blocked needed escalation.

## Frozen gate inputs

| Field | Value at registration |
| --- | --- |
| Gate models | `claude-haiku-4-5-20251001`; `jev-1.13.0`, never an alias (the adapter rejects a response naming another model) |
| Question text and pass rule | as in the registered harness commit |
| State fields and limits | as under "Gate input" above |
| Retries | none |
| Failure behaviour | pass the request |

Repeatability is measured before registration: 20 fixed requests sent 5
times to each gate. If identical requests get different answers, the
spread is reported.

## Rules specific to an external gate

- **Data leaving the machine.** Jev calls send the brief, diff and output to
  TypeSafe. The exp06 task set is already public in this repository, with
  the harvested stratum renamed and reviewed for private content. Tasks
  under `tasks/agentic/private/` are never sent.
- **Billing.** Gate calls are `role = "router"` and count toward cost per
  completed task. A price row for each gate model exists before any run.
- **Isolation.** One run at a time, never alongside another paid run.

## Sample size

52 tasks × 3 trials per arm. exp06's consultation rates imply about 65 to
120 advisor requests per ungated arm on easy work, enough for G2's refusal
rate to about ±10 points before clustering. Cost ratios use task-clustered
intervals as in exp06. Expected spend, before `make dispatch-estimate`:
about $45 for `static_sonnet`, $80 for `ladder_noforce`, and $55 to $80 for
each gated arm, about $250 to $290 in all.

## Threats to validity

| Threat | Handling |
| --- | --- |
| Mostly easy tasks, written by the model family under test | stated as scope; it is the regime the question is about, and the exp06 caveat carries over |
| A gate that refuses everything wins G1 trivially | G3's completion bound and the hard-stratum listing of blocked escalations; refusal on easy work is only good if needed requests still pass |
| Worker text steering the gate | the gate is told to treat state as evidence; passed requests are inspected for completion claims |
| The hook mechanism changes the advisor's cost | both gated and ungated arms use the same mechanism; a fallback is a recorded deviation |
| Vendor claims on calibration and latency | not assumed; only measured values are reported |
| One Jev version, early access | stated as scope; the result is about `jev-1.13.0` |

## Before registering (gates)

1. A headless smoke run showing the hook intercepting the advisor tool:
   one passed and one refused request, with the refusal reason reaching the
   worker, and the advisor's cost unchanged on the passed call.
2. Price rows for both gate models.
3. Repeatability measured.
4. The report prints requests, refusals, gate cost and gate errors per arm,
   and the blocked-escalation listing on the hard stratum.
5. `make dispatch-estimate` within budget, `--budget-usd` set, and the
   operator's go-ahead. Register, commit, then run.

## Open decisions (operator)

| Decision | Proposed | Alternative |
| --- | --- | --- |
| Which gate arms to run | both, so G4 can be tested | Haiku only, if Jev access or price is a problem |
| Send the harvested stratum to TypeSafe | yes; it is already public in this repo | fixture strata only, and G1 to G3 on 36 tasks |
| If the hook cannot intercept the advisor | MCP `request_advisor` fallback, recorded as a deviation | stop, and report exp07 as not feasible on this harness |

## Deviations

None. Not yet registered.

## History

- 2026-10-02: re-scoped from "Jev as handoff verifier and router" (J1 to
  J5, conditional on exp06 H0) to the over-escalation gate, after exp06
  closed. The earlier draft is in this file's git history.
