# 2026-09-23 · exp05 difficulty calibration (66 tasks × Haiku/Sonnet/Opus × 2 trials)

Real run on the Claude track (`exp05_calibrate`, subscription login,
`claude` 2.1.278, harness `03c9c9a`..`bb7fba6`): every task in
`tasks/agentic/tasks.jsonl` on each static candidate, two trials, randomized
block order, 40-turn cap. 396 graded cells, **$109.60** list price. Not a
hypothesis test: it measures what each model finds hard so the confirmatory
run can stratify on measured labels instead of guesses.

## Pass rates

| task generation | n tasks | Haiku | Sonnet | Opus |
|---|---:|---:|---:|---:|
| `-01` (original) | 30 | 60/60 (100%) | 60/60 | 60/60 |
| `-02` (hard batch) | 24 | 35/48 (73%) | 48/48 | 47/48 |
| `-03` (hard batch) | 12 | 14/24 (58%) | 22/24 | 22/24 |
| **all** | 66 | **109/132 (83%)** | 130/132 | 129/132 |
| hard batches only | 36 | 49/72 (68%) | 70/72 | 69/72 |

Measured labels (`make dispatch-calibration ... WRITE=1`, now in
`tasks.jsonl` with the per-model rates under `measured`): easy 50,
medium 15, unsolved 1. No task was "hard" in the measured sense (passed
only by Opus): where Haiku fails, Sonnet almost always passes, so the
routing headroom on this set is Haiku-vs-Sonnet, not Sonnet-vs-Opus.

Haiku failed both trials on six tasks (`inv-rfref-03`, `log-tz-02`,
`log-writer-02`, `notes-ics-03`, `notes-priority-02`, `notes-recur-03`) and
one of two on nine more. 23 sessions hit the 40-turn cap; most had already
solved the task (graded as-is) and only some were failures.

## Costs per session (list price)

| | Haiku | Sonnet | Opus |
|---|---:|---:|---:|
| `-01` tasks | $0.09 | $0.07 | $0.26 |
| hard tasks | $0.28-0.46 | $0.09-0.15 | $0.63-0.89 |

Sonnet was both cheaper than Haiku on the hard tasks (it stops when done;
Haiku keeps exploring) and passed 97% of them.

## Excluded task

`inv-aging-03`: 0/6 across all three models, every failure on the same
hidden test (US-format issue dates). The rule is in the module docstring the
brief points to, but no model treated it as a requirement, so the task
measures a gotcha, not capability. Moved to `tasks/agentic/excluded.jsonl`
with the reason; the active set is **65 tasks**.

## Headroom gate

The pre-registration doc's gate is "the cheapest model passes about 50-70%
of the registered set". Measured: 83% over all 65 tasks, 68% over the 35
hard-batch tasks. Options recorded for the decision before registering:

1. Register all 65 tasks (198 paired task-trials at 3 trials). Haiku
   headroom 17% overall; the primary comparison does not need Haiku to
   fail, but the `static_haiku` baseline will be hard to beat on cost.
2. Register the 35 hard-batch tasks only (105 paired at 3 trials; 68%
   Haiku headroom). Fewer paired trials; the power note must be
   re-checked against the measured discordance.
3. Add another batch modelled on the six tasks Haiku failed twice (spec
   compliance, timezone-aware datetimes, writer/reader state, migrations
   with backward compatibility) and re-calibrate that batch only.

## Incident

Mid-run the account hit its monthly spend limit. The harness at that
commit only recognised "usage limit reached" and graded 216 limit-errored
cells as fails. Fixed in `bb7fba6` (every limit wording pauses the run;
`--resume` sets poisoned cells aside and redoes them); the 216 cells were
redone cleanly and are kept in `outcomes.poisoned.jsonl` for audit. No
poisoned cell is in the table above.

Raw data: `results/exp05_calibrate/20260923-135345` (auto-backed-up to the
Google Drive folder).
