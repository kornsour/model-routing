# Pre-registration: exp08, a Jev gate on advisor requests

Status: **draft, not yet registered (2026-10-02).** Runs after exp07
(`../exp07-evidence-prompt/preregistration.md`), whatever exp07 finds.
Every run is exploratory until the gates in "Before registering" are met.

## History of this design

- **Until 2026-10-02 this was exp07**, "Jev as handoff verifier and
  router" (hypotheses J1 to J5). It was conditional on exp06 finding
  headroom. exp06 closed without it: 5 of 55 tasks were hard, against a
  bar of 10.
- **2026-10-02: re-scoped** to a gate on unjustified advisor requests,
  which is the cost exp06 measured on easy work.
- **2026-10-02: design review.** A separate model instance (Claude Fable
  5.1) reviewed the re-scoped draft. It found that exp06's standing
  instruction to consult the advisor "always before you declare the task
  done" confounds a gate with the prompt it overrides. The prompt question
  was split out as exp07, which runs first. This experiment was renumbered
  exp08 and revised against the review (see "Design review").
- The earlier drafts are in this file's git history (path
  `docs/experiments/exp07-jev-gate/`).

exp08 is a separate experiment with its own registration. No registered
field of exp05, exp06 or exp07 changes because of it.

## Question

When a Sonnet 5.5 worker asks to consult a frontier (Opus 5.5) advisor, can
Jev, a third-party decision model, refuse the requests the worker does not
need, and so lower cost per completed task without lowering completion?
And does Jev decide differently from a cheap generic model or a fixed rule
asked the same thing?

## Shared protocol

exp08 inherits the exp06 protocol (`../exp06-route-on-evidence/paper.md`,
v0.3) wherever this document is silent:
- the paired randomized block design and 3 trials;
- turn caps of 40, and 80 for the long-horizon stratum;
- intention to treat, with provider outages redone;
- task-clustered bootstrap intervals;
- analyst blinding;
- one paid run at a time, an hour after any other.

## Task set

The same 52 tasks as exp07: the pooled exp06 set minus its 3 unsolved
tasks, frozen by hash.
- **45 easy:** the primary set.
- **2 medium and 5 hard:** reported descriptively.

## The base arm is fixed by exp07

The gate sits on top of an advisor-equipped Sonnet session. Which worker
instruction that session uses is decided by exp07's result, by a rule fixed
now:
- **exp07 E1 supported:** the base uses exp07's evidence-gated note.
- **E1 not supported or inconclusive:** the base uses exp06's standing note.

Either way, Jev has to earn its cost against the cheapest prompt-only
alternative known when exp08 registers. The chosen base is recorded at
registration.

## Arms

| Arm | What happens | Role |
| --- | --- | --- |
| `static_sonnet` | Sonnet 5.5, no advisor, no verifier, no handoff | control: the no-advisor floor |
| `base` | the advisor arm chosen above (Opus 5.5 advisor, deployable verifier, K = 2, clean handoff, `ESCALATE` honoured, no forced check); the gate hook runs in **log-only** mode | ungated comparator |
| `base_gate_jev` | identical to `base`, but the hook sends each advisor request to `jev-1.13.0` and refuses it when Jev says it is not justified | gated arm |

`base` and `base_gate_jev` differ only in the gate's decision: same prompt,
same hook, same logging.

**Gate input (frozen).** Everything is bounded and rendered in UTF-8:
- the brief;
- the worker's question to the advisor;
- the first 24,000 characters of `git diff` against the starting commit;
- the last 4,000 characters of worker output, and the same of visible test
  output.

Hidden tests are never in the sandbox, so they cannot reach the gate.

**Gate questions (frozen wording).** Two, each answered yes or no with a
short reason:
1. Has the worker hit evidence it cannot resolve alone? That means a
   failing check it has already tried to fix, a recurring error, or a
   requirement that the brief and the material above do not settle.
2. Does the brief or the material above already answer the worker's
   question?

The request passes if (1) is yes and (2) is no.

**After a refusal.** The worker gets the gate's reason as the tool result
and continues. A session may make at most **5 gate calls**. From the sixth
request on, requests are refused without a gate call, with the message "no
further consultations this session".

**Gate failures.** An HTTP error, timeout, invalid response or rate limit
**passes** the request: a gate that fails closed would turn outages into
blocked escalations. If more than 5% of requests hit a gate failure, the
run is downgraded to exploratory.

**Request accounting.** The harness currently counts every `advisor`
`tool_use` block as a consultation, and a refused request still produces
one. exp08 therefore records three counters per session from the hook log:
- `requested`;
- `passed`;
- `refused`.

Each is cross-checked against the transcript's tool results. Advisor cost
is attributed to passed requests only.

## Offline replay (no worker sessions)

After the live run, the **logged requests from `base`** are replayed
through three gates, each seeing exactly the logged gate input:
- **Jev** (`jev-1.13.0`);
- **Haiku 4.5**, asking the same two questions with the same wording;
- **the rule gate**, which is exp07's deterministic evidence label used as
  a gate: it passes a request only when the worker's recent output shows a
  failing check or a repeated error. It costs nothing.

The replay costs gate calls only, a few dollars. Its scope:
- **Primary data:** each session's **first** request. Later requests depend
  on the advisor's earlier answers, which a gated worker would not have
  seen.
- **Secondary data:** all requests.
- **Checking the replay:** Jev's replay decisions are compared with its
  live decisions, for first requests and for later ones separately.
- **What replay cannot show:** how a worker behaves after a refusal. That
  is measured live, for Jev only.

## Hypotheses

Cost per completed task includes every session and every gate call. Gate
calls are billed `role = "router"`.

**Primary. G1 (Jev lowers cost without lowering completion).** On the 45
easy tasks, `base_gate_jev` has a lower cost per completed task than
`base`, with completion non-inferior to `base`:
- **cost:** the one-sided 97.5% upper bound of the cost ratio is below 1.0;
- **completion:** the one-sided 97.5% lower bound of the paired completion
  difference is above −5 points.

Secondary, Holm-adjusted as one family of two, each with a p-value from a
task-clustered permutation or bootstrap:

| # | Hypothesis | Test |
| --- | --- | --- |
| G2 | Jev refuses more easy-task requests than it needs to pay for itself: the refusal rate is above the break-even rate r* = c / a. Here c is the mean Jev cost per gate call and a is the mean advisor cost per consultation, both measured in this run. | lower 97.5% bound of the refusal rate above r* |
| G3 | On identical first requests from easy tasks, Jev and the Haiku gate refuse at rates within 10 points of each other. | two one-sided tests (TOST) at ±10 points, pairs resampled by task |

**Verdicts.** Each hypothesis gets one of three verdicts:
- **supported**, when the interval clears its bound;
- **not supported**, when the interval lies wholly on the wrong side of
  the bound;
- **inconclusive**, otherwise.

A G3 "not supported" says the two gates differ. The direction is reported
against the rule label. It is not a claim that one gate is more accurate.

**Descriptive, no verdict.**
- **Replay agreement:** pairwise agreement among Jev, Haiku and the rule
  gate. Each model gate's refusal and pass rates on rule-labelled and
  unlabelled requests, which serves as a manipulation check that each gate
  follows its own two questions.
- **Per arm:**
  - requests, passes and refusals per session;
  - the advisor's share of cost;
  - the Jev gate's cost per call and its error rate;
  - the handoff and `ESCALATE` rates. A refused worker may escalate to a
    full Opus session instead, and that cost is already inside cost per
    completed task. A sensitivity row shows the cost with handoff
    sessions removed.
- **On the 7 hard and medium tasks:**
  - completion per arm, per cell;
  - the count of cells where `base_gate_jev` refused a request and then
    failed while `base` passed the same task and trial. This is shown
    beside the chance rate implied by static Sonnet's calibrated pass rate.
- **The full request table:** one row per request, with task, trial, turn,
  arm, rule label, Jev live decision, and the Jev, Haiku and rule replay
  decisions.

**Few-events rule.** If `base` logs fewer than 40 first requests on easy
tasks, G2 and G3 are reported descriptively, with no verdict. This is
likely if exp07's evidence note becomes the base, and it is itself a
finding: there would be little left for a gate to refuse.

**Planning values.** These are recomputed from exp06 and exp07 cell data
and recorded here before registration. If `base` sits near 1.85× plain
Sonnet and Jev refuses most requests, G1's cost ratio is near 0.6 and well
powered. If the base is exp07's evidence arm near 1.1×, there is little for
the gate to remove. G1 is then likely inconclusive, and that is the
expected and correct reading.

## Performance

The question asks whether Jev can "reduce cost while improving
performance". A gate can only remove consultations. On this task set,
completion can rise only where Sonnet fails, and that happens on 7 tasks.
exp06 never showed the advisor helping there.

So exp08 tests the cost side with a non-inferiority bound on completion.
Any completion gain is reported descriptively on the hard and medium cells.
A performance claim would need a hard-task set that exp06 could not build
at scale (see "Open decisions").

## What this experiment can and cannot claim

It can claim, with intervals:
- "On 45 easy coding tasks, a Jev gate in front of Claude Code's advisor
  refused X% of advisor requests and moved cost per completed task from Y×
  to Z× plain Sonnet, with completion within M points of the ungated arm."
- "On identical logged requests, Jev and a Haiku 4.5 gate asking the same
  questions agreed on N%, and differed in refusal rate by D points."
- "A fixed rule on the worker's recent output refused R% of the same
  requests."

It cannot claim:
- that Jev, or any gate, tells needed escalations from unneeded ones;
  there is no per-request ground truth and almost no hard work;
- that an advisor with a gate beats having no advisor;
  `static_sonnet` is the floor, and it is reported;
- anything about other harnesses, vendors, Jev versions, or tasks not
  written by the Claude family.

## Frozen at registration

| Field | Value |
| --- | --- |
| Models | `claude-sonnet-5-5`; advisor `claude-opus-5-5`; gate `jev-1.13.0`, never an alias (the adapter rejects a response naming another model); replay gate `claude-haiku-4-5-20251001` |
| Base arm | as chosen by the rule above, with the worker note verbatim |
| Gate questions, input bounds, pass rule, call cap, failure behaviour | harness commit |
| Rule-gate regexes | identical to exp07's, at the harness commit |
| Claude Code version | one version for the whole run, recorded per session |
| Analysis | an `exp08` analysis module implementing G1 to G3, the replay and the descriptive tables, committed, hashed into the config, and dry-run on the fake provider |
| Task set | by hash |

**Repeatability, before registration:** 20 fixed requests, each sent 5
times to Jev and to Haiku. The live arm uses a single call. Any spread
across the 5 calls is reported, not averaged away.

## Rules specific to a third-party gate

- **Data leaving the machine.** Jev calls send the brief, diff and output
  to TypeSafe. The task set is already public in this repository, with the
  harvested stratum renamed and reviewed for private content. Nothing from
  `tasks/agentic/private/` or a hidden test directory is ever sent.
- **Billing.** Gate calls are `role = "router"`. A `pricing.toml` row for
  `jev-1.13.0` exists before any run.
- **Isolation.** One paid run at a time.

## Threats to validity

| Threat | Handling |
| --- | --- |
| The gate is confounded with the worker instruction | exp07 runs first; the base arm uses the cheaper instruction if it works |
| Refusing everything wins on easy tasks | stated: on easy tasks every refusal saves money, so G1 measures the cost side only; the hard-cell listing, the handoff rate and the request table show what refusals cost |
| A refused worker escalates to a costlier rung | handoff rate reported; cost per completed task includes it; sensitivity row |
| Replay is not a live counterfactual | first requests are primary; Jev live-vs-replay agreement is reported |
| The hook changes the advisor's cost | both advisor arms run the hook |
| Worker text steering the gate | the gate is told to treat state as evidence; every request and decision is published in the request table |
| Vendor claims about calibration or latency | not assumed; only measured values are reported |
| One Jev version, early access | stated as scope |

## Before registering (gates)

1. exp07 is complete, and the base arm is chosen by the rule above.
2. A Jev adapter exists, with no Jev code in the harness today. It also
   needs a price row and the TypeSafe access terms reviewed by the
   operator.
3. Hook smoke run in headless mode showing:
   - one passed and one refused request, with the refusal reason reaching
     the worker;
   - the three counters correct;
   - the advisor's cost unchanged on passed calls.
4. Repeatability is measured.
5. The analysis module is dry-run on the fake provider.
6. A pilot of 5 tasks × 1 trial of `base_gate_jev` (about $3), excluded
   from analysis, to observe refusal loops.
7. `make dispatch-estimate`, then `--budget-usd` set, then the operator's
   go-ahead. Register, commit, then run.

## Sample size and budget

52 tasks × 3 trials × 3 live arms = 468 cells. Expected list cost:
- `static_sonnet`: about $45;
- `base`: $55 to $80, depending on which base is chosen;
- `base_gate_jev`: $50 to $80, plus Jev calls at a price not yet known;
- replay and pilot: about $10.

That is about **$160 to $215 plus Jev fees**. This is a **new budget**,
beyond exp06's $500, which exp07 will mostly use up; it needs the
operator's approval.

Budget priority if a pause hits: finish `base_gate_jev`, then `base`, then
`static_sonnet`. A `static_sonnet` shortfall falls back to exp07's fresh
Sonnet run, as a recorded deviation.

## Open decisions (operator)

| Decision | Proposed | Alternative |
| --- | --- | --- |
| A live `always_refuse` arm (advisor present, every request refused) as a lower reference | no; `static_sonnet` is the floor | yes, about $50 more; it separates "refuse everything" from "no advisor" |
| A larger hard-task set so performance can be tested | no; cost-side study only | build and calibrate more long-horizon tasks (3 of 12 were hard in exp06) before exp08; weeks of work plus about $100 of calibration |
| If Jev access or price is a problem | run the Haiku gate live in its place, as a recorded deviation | stop |

## Design review

Reviewed 2026-10-02 by Claude Fable 5.1, read-only, against the combined
draft. What was done with each point:

| Review point | Disposition |
| --- | --- |
| No prompt-only control: the gate is confounded with the instruction | split out as exp07, which runs first; the base arm is chosen by its result |
| On easy tasks the design rewards refusal; harm is barely measurable | stated as scope; paired refused-then-failed count with a chance baseline; `always_refuse` left as an open decision |
| No per-request ground truth | deterministic rule label and rule gate; all claims worded as agreement, not accuracy |
| Refusal can push the worker to a costlier handoff | handoff rate, sensitivity row, 5-call cap |
| The harness miscounts refused requests | three counters from the hook log; checked in the smoke run |
| G1 likely inconclusive at 1.25× | G1 now compares against `base` (superiority plus non-inferiority); planning values required |
| Replay selection effect | first requests are primary; live-vs-replay agreement is split by request order |
| G1 mixes references; non-inferiority unexplained | one-sided 97.5% bounds against `base`; `static_sonnet` reported alongside |
| "Half of requests" contradicts the break-even | G2 is now the measured break-even |
| G4 was an equivalence claim with a superiority rider | G3 is a TOST; no advantage claim |
| Holm needs p-values | specified per hypothesis |
| Few events; gate error ceiling; truncation; analysis frozen; one CLI version; pilot; full request table | all adopted |
| Gate question (2) asked about the repo, which the gate cannot see | reworded to "the brief or the material above" |

## Deviations

None. Not yet registered.
