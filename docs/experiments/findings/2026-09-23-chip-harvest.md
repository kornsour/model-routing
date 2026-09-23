# 2026-09-23: Real handoffs vs the synthetic task set (chip harvest)

Issue #11 item 4 asks whether the synthetic agentic task set
(`tasks/agentic/tasks.jsonl`, 54 briefs at the time of writing) looks like
the task chips people really hand off. This note compares aggregate
statistics for the two.

## Data and method

- **Harvest date:** 2026-09-23, via `make harvest-chips`. No model calls and
  no network. The harvester ran on the local transcript layout without changes.
- **Source:** the operator's local Claude Code transcripts, from late
  2026-07 to 2026-09-23. There are 562 unique handoff prompts from 66 parent
  sessions across 29 local projects. 59 are `spawn_task` chips and 503 are
  subagent dispatches (`Agent`/`Task` tool calls).
- **Privacy:** the raw output (`tasks/agentic/private/harvested.jsonl`) is
  git-ignored and exists only on this laptop. This note contains aggregates
  only: no prompt text, titles, paths, or project names.
- **Script:** `uv run python scripts/chip_stats.py` computes every number
  here. Its heuristics are stdlib keyword regexes, unit-tested on synthetic
  strings in `tests/test_chip_stats.py`.
- **Caveat on categories:** the category heuristic is coarse. On the
  synthetic set it matches the human `category` label for only 27 of 54
  briefs (50%). Several of those labels are debatable too, for example the
  CSV-quoting "features" read like bugfixes. To compare like with like, the
  table applies the same heuristic to both sides. Read the category rows as
  rough shape only, not as a precise mix.
- **Single operator:** every sample comes from one operator. A parent model
  wrote each harvested prompt. The operator did not type them.

## Side by side

| metric | synthetic briefs | harvested: all | harvested: `spawn_task` chips | harvested: subagent dispatches |
|---|---|---|---|---|
| items (n) | 54 | 562 | 59 | 503 |
| chars min / median / p90 / max | 454 / 1076 / 1331 / 1607 | 11 / 4154 / 6540 / 10889 | 941 / 1991 / 2934 / 4031 | 11 / 4353 / 6726 / 10889 |
| ~tokens (chars/4) min / median / p90 / max | 114 / 269 / 333 / 402 | 3 / 1038 / 1635 / 2722 | 235 / 498 / 733 / 1008 | 3 / 1088 / 1682 / 2722 |
| mentions tests | 100% | 51% | 64% | 50% |
| names at least 1 file path | 100% | 96% | 100% | 95% |
| multi-file (2 or more paths) | 100% | 90% | 97% | 90% |
| explicit scope/constraint sentence | 100% | 87% | 44% | 92% |
| spawned with explicit model field | n/a | 54% | 0% (the tool has no such field) | 60% |
| names a model in the text | 0% | 34% | 8% | 37% |
| category: bugfix | 39% | 30% | 59% | 27% |
| category: feature | 26% | 11% | 0% | 13% |
| category: refactor | 7% | 3% | 3% | 3% |
| category: tests | 0% | 0% | 0% | 0% |
| category: docs | 9% | 21% | 19% | 21% |
| category: config | 4% | 22% | 15% | 23% |
| category: migration | 0% | 1% | 0% | 1% |
| category: perf | 6% | 1% | 2% | 1% |
| category: investigation | 0% | 10% | 2% | 11% |
| category: other | 9% | 1% | 0% | 1% |

**Handoffs per parent session:**

- All kinds: median 6, p90 22, max 55. Of the 66 sessions, 18 spawned 1
  handoff, 12 spawned 2-3, 21 spawned 4-10 and 15 spawned 11 or more.
- `spawn_task` chips only: median 2, max 5. Of the 32 sessions that spawned
  chips, 16 spawned 1, 14 spawned 2-3 and 2 spawned 4-10.

**Subagent routing already in use:**

- 304 of 503 dispatches set an explicit model: 271 `sonnet` and 33 `opus`.
  None set a Haiku-class model.
- Subagent types: 376 general-purpose, 93 unset, 31 Explore and 3 Plan.

## How representative is the synthetic set?

**Partly representative.** The synthetic briefs have the right structure:
they name files, touch more than one file, and state acceptance criteria.
They differ from real handoffs in length, in how uniform their wording is,
and in their category mix.

- **Too short.** The median synthetic brief is about 270 tokens. That is
  about half a real `spawn_task` chip (about 500) and a quarter of a real
  subagent dispatch (about 1,100). The longest synthetic brief (about 400
  tokens) is shorter than the median real chip. Real handoffs also have a
  long tail, up to about 2,700 tokens, that the synthetic set lacks entirely.
- **Too uniform in scope and tests.** Every synthetic brief ends with a
  scope line and mentions tests, by design. Real chips carry an explicit
  scope sentence only 44% of the time and mention tests 64% of the time.
  Subagent dispatches are usually constrained (92%) but mention tests only
  half the time. The scope line is still right for grading fairness (see the
  2026-09-22 pilot). It does mean the full `brief` sits at the "well
  specified" end of the real distribution. `brief_terse` sits below the real
  distribution rather than in the middle of it.
- **File naming matches.** 100% of synthetic briefs name files and are
  multi-file, versus 96-100% and 90-97% for real handoffs.
- **Category mix is skewed.** Real chips are mostly bugfix (about 60%),
  followed by docs and config (about 35% combined). The synthetic set's docs
  and config share is small (about 13% by the heuristic, 8 of 54 by label).
  Its feature share is higher than in real handoffs. Read-only
  investigation, about 10% of real dispatches, has no synthetic
  counterpart. Migration and perf are rare in real handoffs, so the four
  migration and three perf tasks in the `-02` batch over-represent them.
  They are still defensible as routing-headroom probes.
- **Model choice in real use is a two-way choice.** Parents already route
  subagent work between Sonnet and Opus, about 9 to 1, and never pick
  Haiku. That is outside evidence that the study's candidate ladder is the
  real decision. It also makes a cheap-tier arm worth testing, because no
  one currently routes there.

## Recommendations for the next task batch

1. **Lengthen briefs.** Target a median of about 500 tokens and a p90 of
   about 750, to match real chips. Add a long-brief stratum of 1,000-2,500
   tokens that looks like subagent dispatches: background, prior findings,
   and several numbered steps.
2. **Vary how the brief is specified, not whether the scope is graded.** Keep
   `allowed_paths` grading. Write about half of the new briefs so the scope
   appears only as prose ("keep this to the CLI module") or is implied,
   without the verbatim `Scope:` line. Also drop the test instruction from
   about a third of them. This matches the 44% and 64% real rates, and it
   tests hypothesis H-D6 (brief quality) inside the realistic range rather
   than only at its two ends.
3. **Rebalance categories toward what people hand off:**
   - more bugfix, including multi-step bugfixes;
   - more config and tooling tasks: CI, lint settings, packaging metadata,
     environment and flag wiring;
   - more docs tasks that need code reading, such as bringing a README or
     docstrings in line with actual behavior. A badge swap is not enough;
   - fewer net-new features.
4. **Add a read-only investigation stratum**, about 10% of the set. The
   agent answers a question about the fixture repo in a fixed, parseable
   format. Grade it deterministically against an answer key, for example a
   set of file/function names or a number, with an empty-diff scope check.
   The set currently has no tasks of this kind.
5. **Keep migration and perf small**, about 5% each. Label them as headroom
   probes in the pre-registration so they are not read as representative
   of real handoffs.
6. **Re-run this comparison** (`make harvest-chips` then
   `scripts/chip_stats.py`) after each new batch, and before freezing the
   confirmatory set. Record the updated numbers as a new findings note. Do
   not edit this one.
