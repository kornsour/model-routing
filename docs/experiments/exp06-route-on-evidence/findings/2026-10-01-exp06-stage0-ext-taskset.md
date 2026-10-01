# 2026-10-01 · exp06 Stage 0 extension: the 40-task set (built, validated, not yet run)

Step 1 of the extension plan (`../extension-plan.md`): build the 40 new
tasks in four strata, review the harvested stratum for private content,
validate every task, and compare brief statistics with real handoffs. No
model has been run on any of these tasks, and nothing here cost money.

- Task file: `tasks/exp06/tasks_ext.jsonl` (40 tasks, sha256 `e9bc5a1114e4aa73…`),
  built by `uv run python tasks/exp06/build_tasks.py` from `tasks/exp06/briefs/*.md`.
  The first batch, `tasks/exp06/tasks.jsonl` (sha256 `25ffd0c4fc1f9340…`), is
  rebuilt byte-for-byte unchanged.
- Validation: `uv run python scripts/validate_agentic_tasks.py tasks/exp06/tasks.jsonl tasks/exp06/tasks_ext.jsonl`.
  All 55 tasks pass: the untouched fixture fails grading, the reference
  solution passes, and the visible checks are green (3 min 8 s on the
  operator's laptop). This is not in CI: the new fixtures need `git`, Go 1.22+
  and Node 22.18+ (TypeScript type stripping on by default) on the grading host.
- `make check` is green (ruff, format, pyright, 400 tests).

## What was built

| stratum | n | where | shape | turn cap |
|---|---:|---|---|---:|
| A. harvested handoffs | 16 | 15 new fixture repos | the drawn brief, renamed, with a short offline note | 40 |
| B. long-horizon, multi-package | 12 | new `platform` monorepo (`orchestra` + `toolbelt` + new `ledger`) | dispatch-shaped briefs: background, prior findings, numbered requirements, constraints, report-back | 80 |
| C. ambiguous | 6 | `toolbelt`, `orchestra`, `platform` | chip-length asks with one requirement left out; the repo holds the answer; answer key in front matter | 40 |
| D. read-only investigation | 6 | `orchestra`, `toolbelt`, `platform` | questions answered in a fixed `ANSWER.json`; any other file change fails | 40 |

Languages and tools the agent needs: Python everywhere; Go (`ha-endedat-14`);
TypeScript run by Node 24 without a build step (`ha-cron-auth-15`,
`ha-headline-09`, `ha-archive-tsstarter-06`, `ha-verify-suite-16`); git
history work (`ha-branch-triage-02/08`, `ha-branch-verdict-11/12`,
`hd-git-archaeology-04`); YAML workflow rewriting (`ha-runner-class-01`,
`ha-ci-adopt-03`).

Graders stay deterministic: hidden pytest files, some of which drive
`node --test`, `go test` or the repo's own CLI. Read-only tasks
(`allowed_paths` = the answer file) grade an answer file against a key.
Four stratum-A investigations and the ruleset sweep originally reported
in prose. Their offline note asks for the same report in `REPORT.md`,
ending in a fixed JSON block, so they can be graded.

### Stratum B in one line each

`hb-money-ledger-01` exact money end to end with a v1→v2 history format;
`hb-heartbeat-02` heartbeat liveness shared by reaper and overlap guard, pause
on SIGTERM; `hb-budget-policy-03` per-pipeline policy where null inherits,
plus admission; `hb-ingest-04` segmented event logs → idempotent ingestion;
`hb-backoff-05` one backoff policy in toolbelt with a deprecated orchestra
shim and a ledger estimator; `hb-report-06` time-zone months, nearest-rank
percentiles, CSV/Markdown; `hb-store-migrations-07` declarative migrations,
chain check and a two-branch numbering collision; `hb-capacity-planner-08`
exhaustive capacity search that survives Graham's anomaly; `hb-config-layers-09`
layered config with provenance and transitive secret redaction;
`hb-audit-chain-10` hash-chained history with checkpoint compaction;
`hb-incidents-11` eight incidents, seven injected bugs across both packages
and one that is documented behaviour; `hb-dashboard-export-12` static JSON
export with unique slugs, critical paths and manifest cleanup.

## The harvested draw and the privacy review

**Draw.** `tasks/exp06/harvest_draw.py` sorts the 562 harvested handoffs by id
and shuffles them with seed `20261001`. Prompts were reviewed in that order
until 16 were accepted; 42 were reviewed. Each decision is recorded, with
harvest ids and reason codes but no prompt text, in `tasks/exp06/harvest_draw.json`.

| decision | n | primary reason |
|---|---:|---|
| accepted | 16 | |
| skipped: needs a live system (GitHub API writes, cloud accounts, live CI logs, sudo) | 8 | no offline grader |
| skipped: needs package installs or a networked build (`pnpm install`, Electron, Neon branches) | 7 | no offline grader |
| skipped: personal data (job search, compensation, named third parties) | 7 | private |
| skipped: real infrastructure security posture or a real credential identifier | 2 | private |
| skipped: open-ended output with no fixed form (UI survey, design judgement) | 2 | no deterministic grader |

**The skip rate is a finding in its own right.** 26 of 42 real handoffs (62%)
cannot become offline, deterministically graded tasks. They live against real
accounts, real databases and real package registries, or they are about the
operator's own life. Stratum A therefore over-represents config, docs, CI and
investigation work and under-represents the operator's main application
code. No accepted prompt was a `spawn_task` chip; the one chip drawn
(position 36) was skipped as private. Read stratum A as "real handoffs that
can be fixtured", not "real handoffs".

**Privacy review (done by Claude Opus 5.5 during the build; it needs the
operator's sign-off before any brief is reused).** The repo is public, so every
accepted brief was checked line by line before reuse:

- Org, personal-account, repository, product, host and person names are
  replaced by fictional ones (`Copperline`, `ellisport`, `mise`, `packlight`,
  `trailhead`/`Pathwise`, …). Absolute paths, scratchpad paths, AWS/GCP
  identifiers, run ids and the owner's site are removed. Each brief records
  its replacements in an `adaptations` front-matter field.
- Prompts whose substance is private were skipped, not redacted. Renaming
  cannot neutralise a real security gap or someone's job search.
- Every fixture is invented. No file content comes from the operator's
  repositories, and the harvested file never leaves `tasks/agentic/private/`.

**Adaptations beyond renaming,** recorded per task: an offline note (no
network, `gh` or remote; `gh` results given inline or in a `gh-snapshot/`
directory; skip push and PR steps); a `REPORT.md` with a JSON answer block
where the original asked for prose; and the history scripts that rebuild the
git state an investigation needs. The JSON block makes those tasks easier to
grade and probably easier to pass than the originals. That is a validity cost.

## Harness changes (exp06 extension only; first-batch behaviour unchanged)

- `grader["history_script"]` (`tasks/exp06/history/<id>.sh`): a bash script
  run in the sandbox after its first commit. It builds branches, tags, a local
  `origin` and nested clones. Each script back-dates the sandbox root, because
  a root younger than its descendants makes `git rev-list A..B` miscount.
- Solution overlays can delete files (`.overlay-delete`), for tasks whose
  answer is a move (archiving docs, renumbering a migration).
- `agent_bash` on a task adds `Bash(...)` patterns to the Claude agent's tool
  allowlist. The default allowlist (`python`, `pytest`, `git status`, `ls`,
  `cat`) cannot run git history, Go or Node. First-batch tasks set none, so
  their conditions are unchanged. Codex ignores the field (its sandbox has no
  per-command allowlist).
- `scripts/validate_agentic_tasks.py` takes task files as arguments.
- Tests: `tests/test_dispatch_task_tooling.py`.

## Brief statistics vs real handoffs

`scripts/chip_stats.py` (aggregates only) against the 562-item harvest.
Token counts are characters / 4.

| set | n | ~tokens min / median / p90 / max | mentions tests | ≥2 file paths | scope sentence |
|---|---:|---|---:|---:|---:|
| first batch | 15 | 433 / 780 / 920 / 1,033 | 100% | 67% | 80% |
| **extension, all** | 40 | 70 / 1,032 / 1,427 / 2,460 | 78% | 78% | 70% |
| A harvested | 16 | 1,009 / 1,295 / 1,629 / 2,460 | 69% | 100% | 100% |
| B long-horizon | 12 | 804 / 1,029 / 1,384 / 1,422 | 100% | 83% | 50% |
| C ambiguous | 6 | 70 / 130 / 173 / 176 | 100% | 0% | 0% |
| D read-only | 6 | 185 / 395 / 506 / 506 | 33% | 83% | 100% |
| harvest: all | 562 | 3 / 1,038 / 1,635 / 2,722 | 51% | 90% | 87% |
| harvest: `spawn_task` chips | 59 | 235 / 498 / 733 / 1,008 | 64% | 97% | 44% |
| harvest: subagent dispatches | 503 | 3 / 1,088 / 1,682 / 2,722 | 50% | 90% | 92% |

Against the plan's targets:

- **Stratum A** median is 1,295 tokens with the offline note and 1,141
  without it. The accepted originals have a median of 1,170. The plan
  expected about 500 (the `spawn_task` median), but a draw from all 562 is 90%
  subagent dispatches, and the stratum matches that population (1,088). The
  target assumed chips; the draw did not produce any.
- **Stratum B** median is 1,029, in the "real dispatch range" (1,000–2,500)
  but at its bottom: 5 of 12 briefs are just under 1,000 tokens (804–998). The
  long-horizon load sits in the work, not in the brief.
- **Stratum C** briefs are deliberately short (median 130 tokens). They are
  shorter than real chips (498) and name fewer files, because the missing
  requirement must be found in the repo. That is the point of the stratum and
  a departure from the chip shape.
- **Mix.** The whole extension mentions tests more often than real handoffs
  (78% vs 51%) and states scope less often (70% vs 87%, pulled down by C).
  On the heuristic's categories it is heavier on feature and docs work and
  lighter on bugfixes (8% vs 30%) and investigation (2% vs 10%). The
  heuristic agrees with the tasks' own labels for only 10 of 40, so read the
  category rows as rough shape; by label, 13 of 40 tasks are investigations.

## Deviations and threats to record before the run

| plan | built | why / effect |
|---|---|---|
| Reference solutions and hidden tests re-derived by a different model family where practical | All fixtures, hidden tests and reference solutions were written by Claude Opus 5.5, the family under test. Each task's `authorship` field records this. | Step 1 was to cost nothing, and `codex exec` re-derivation is paid. The first batch's main validity threat is therefore still present for strata B to D. An independent re-derivation pass before registration would close it. |
| Stratum A briefs kept at their real wording | Kept, plus renames and an offline note; prose reports converted to a JSON answer block | Needed for offline grading; likely makes those tasks easier |
| Stratum C: one missing requirement, answer key for L5 | Each missing requirement can be recovered from a repo artefact (legacy log samples, a docstring, a protocol doc, a runbook). Hidden tests pin the keyed reading. | Under static arms with no simulated user, an unrecoverable gap would only measure luck. This tests careful reading instead. |
| 80-turn cap for stratum B | Set per task (`max_turns: 80`) | **The runner ignores per-task `max_turns`** (`DispatchConfig.max_turns` applies to every session, by design from the 2026-09-22 pilot). Step 2 needs a config switch or two passes before the 80-turn cap takes effect. |
| Harvested draw skips "only when no deterministic grader can be written or the content is private" | Followed. "No grader" includes needing live systems or networked installs, because the sandbox is offline. | See the skip table; stratum A is a filtered sample |

## What this changes for step 2

The calibration config can point at `tasks/exp06/tasks_ext.jsonl` as planned.
Before the run:

1. Give the runner a way to honour per-task `max_turns` (or run stratum B in a
   separate pass with `max_turns = 80`).
2. Make sure the grading host has Go 1.22+ and Node 22.18+ on `PATH`; the
   validator run above is the check.
3. Run `make dispatch-estimate` as usual. The new tasks' briefs are longer
   than the first batch's (median 1,032 vs 780 tokens), and stratum B has
   twice the turn cap.
