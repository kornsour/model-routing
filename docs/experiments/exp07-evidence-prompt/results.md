# exp07 results: evidence-gated advisor prompt

Status: **closed 2026-10-06; confirmatory** (the run matches the
pre-registration: task-set hash, n_tasks 52, harness commit 573dce5,
CLI 2.1.285, frozen files unchanged). Deviations: none.

Run: `results/exp07_evidence_prompt/20261005-113028`. That is 52 tasks × 3
trials × 3 arms, 468 graded cells, $159.17 total spend. The run was started
2026-10-05 11:30 and finished overnight. The full analysis output is in
[`findings/exp07-analysis.md`](./findings/exp07-analysis.md).

## Headline

Changing one sentence of the advisor note ("consult it only when you have
evidence you cannot resolve alone…") **cut cost per completed task on easy
work by 39% (ratio 0.61, 95% CI 0.55 to 0.69). Completion was unchanged:
0.0 points (95% CI −3.7 to +3.0) against a −10-point margin.** E1 is
supported.

The mechanism is blunter than the hypothesis assumed. **The evidence-gated
worker never consulted the advisor at all**: 0 requests in 156 cells. That
held even though it went through 44 verifier "checked and not accepted"
resumes, which is exactly the evidence the note allows it to consult on. In
practice the wording works as an off switch, not as a gate.

## Hypotheses (45 easy tasks, the primary set)

| | estimate [95% CI] | bound | verdict |
|---|---|---|---|
| E1 cost: evidence / standard | 0.61 [0.55, 0.69] | upper < 1.0 | supported |
| E1 completion: evidence − standard, pts | 0.0 [−3.7, 3.0] | lower > −10 | supported |
| **E1** | | both | **supported** |
| E2: evidence / static Sonnet | 1.16 [1.08, 1.27] | upper < 1.25 | inconclusive (Holm p 0.057) |
| E3: evidence-labelled share of requests | n/a | lower > 0 | not estimable (0 evidence-arm requests; few-events rule) |

## Arms (all 52 tasks)

| arm | pass rate | cost per completed task (95% CI) | advisor requests | verifier resumes | escalations |
|---|---|---|---|---|---|
| `ladder_evidence` | 92% | $0.318 ($0.273 to $0.373) | 0 | 44 | 5 |
| `ladder_noforce` | 92% | $0.518 ($0.426 to $0.625) | 88 (61% of cells had none) | 36 | 6 |
| `static_sonnet` | 90% | $0.279 ($0.239 to $0.326) | n/a | n/a | n/a |

In `ladder_noforce` the advisor took 30% of spend. The median advisor input
was 44.8k tokens per counted request, which is above the ~31k floor for a
real read, so the block-id dedupe from the pilot held. 43% of its requests
on easy tasks carried failure evidence under rule v2.

## What this means

1. **The advisor's idle cost is a prompt problem, and it is cheap to fix.**
   exp06 found the ladder losing to plain Sonnet mainly because of advisor
   reads on work that didn't need them. One sentence removes that cost with
   no measurable loss in completion.
2. **It does not make the ladder cheaper than plain Sonnet.** The
   evidence-gated ladder still costs about 1.16× static Sonnet on easy work.
   The bound was 1.25× and its interval just crosses it, so E2 is
   inconclusive. The leftover overhead comes from the verifier, resumes and
   escalation, not from the advisor. Always-Sonnet is still the cheapest
   policy, consistent with exp05 and exp06.
3. **The gate didn't discriminate.** A worker that never calls the advisor
   cannot show whether evidence-gated calls are more useful (E3). Any
   advisor value on medium or hard tasks is also lost. On the 7 medium and
   hard tasks the arms are too few to compare: `hb-money-ledger-01` passed
   3/3 under the evidence arm and 0/3 under noforce, while
   `hb-config-layers-09` went the other way. Both are descriptive only.

## Consequences for exp08 (Jev gate)

exp08 planned to replay exp07's advisor request log. The evidence arm logged
no requests, so the only request log is `ladder_noforce`'s: 88 stream-captured
requests, 43% labelled as carrying evidence. That is a usable replay set, but
small. exp08's pre-registration needs a deviation or amendment before
registration that names this source and its size.

## Notes

- The PreToolUse hook recorded 0 advisor requests. This was expected: Claude
  Code doesn't fire hooks for the server-side advisor tool. All requests come
  from stream capture, and diffs come from the PostToolUse snapshot.
- 31 usage-limit pauses (2026-10-05 15:20 to 17:30) redid one
  `static_sonnet` cell with no wasted spend. Usage-limit pauses don't count
  as set-aside cells.
- Claude Code auto-update was frozen at 2.1.285 for the run and was
  re-enabled afterwards (`make cli-unfreeze`, 2026-10-06).
