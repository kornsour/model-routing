# Dispatch-time routing: does choosing the model when work is handed off save money?

## The claim under test

Assistants already split work: a parent session spawns a separate task (a
"task chip", a subagent, a background job) with a self-contained brief. The
spawner has full context and is already writing the brief, so asking it to
also pick the model is nearly free. A fresh session starts with a cold cache
whatever model runs it, so routing there does not fragment a cache, and there
is no mid-session model switch to degrade output.

**Primary hypothesis (H-D1).** Spawning with the model the parent recommends
*while it writes the brief* (policy `C1_inline`) has a lower cost per
completed task than spawning with the parent's own model (policy `B`), with
a pass rate no more than the non-inferiority margin (10 points) worse.

This is pre-registered: the metric, margin, policies, ordering, trial count
and the task-set hash are frozen in the `[preregistration]` table of
`experiments/agentic/exp05_dispatch.toml` before the confirmatory run (see
[`preregistration-exp05.md`](preregistration-exp05.md) for the full analysis
plan and the gates that must be met first). The report only calls a run
*confirmatory* when it matches that table; everything else is exploratory.
Pilot and calibration runs size variance, cost and task difficulty; they do
not test H-D1.

## Secondary hypotheses

| # | Hypothesis | Comparison (expected winner first) |
|---|---|---|
| H-D2 | Doing the task inside the parent session costs more per completed task than spawning with a brief, because every turn re-reads the parent's context. | `B` vs `A` |
| H-D3 | Switching model mid-session costs more than staying (cache rewrite) and passes less often. | `A` vs `A_switch` |
| H-D4 | A cheap-first cascade that escalates only when the checker fails beats a single routed pick when a real checker (tests) exists. | `D` vs `C1` |
| H-D5 | Parent-recommended routing beats a context-free router (classifier/heuristic on the brief alone) at lower router overhead. | `C1` vs `C2` |
| H-D1p | Pessimistic routing: even a forked router call that re-reads the whole parent context (`C1`) beats `B`. | `C1` vs `B` (reported via H-D5/H-D4 context; not a verdict) |
| H-D6 | Brief quality matters as much as model choice: the cheap model with the full brief beats it with a terse brief by more than the cheap-vs-parent model gap. | `static_cheap` vs `static_cheap_terse` |
| H-D7 | An oracle (cheapest model that passed, in hindsight) bounds the saving; deployable policies recover part of it. | `oracle` (computed, not run) |

## Policies

| Policy | What happens | Parent session needed |
|---|---|---|
| `A` | Resume the seeded parent session; do the task there on the parent model | yes |
| `A_switch` | Resume the seeded parent session but with `switch_to` model | yes |
| `B` | Fresh session, parent model, full brief | no |
| `C1` | Resume parent (forked) and ask it for `{model, effort, reason}` from the menu (a separate router call that re-reads the parent context: the *pessimistic* routing overhead), then fresh session on that pick | yes |
| `C1_inline` | Resume parent (forked) and ask it to write the chip brief *and* end with the `{model, effort, reason}` pick in one turn, as a real spawner does. The whole turn is recorded, but only the pick's marginal tokens (menu + instruction in, one JSON line out, chars/4) are billed as router overhead; the worker then runs on the canned brief so `C1_inline` and `B` differ only in the model | yes |
| `C2` | Classifier/heuristic on the brief alone picks the model, then fresh session | no |
| `D` | Fresh session on the cheapest model; check it (something in scope changed, nothing out of scope changed, visible tests pass); on failure, escalate to the next model in `chain` with the failure log | no |
| `D_ideal` | Same cascade, but the hidden tests are the checker: an upper bound for any cascade, not deployable | no |
| `static:<cand>` | Fresh session on a fixed candidate (also feeds the oracle) | no |
| `oracle` | Computed in the report from `static:*` outcomes | — |

Seeding a parent session (loading `parent_context`) is billed with
`role = "setup"`. It is a sunk cost in reality, so it is reported but
**excluded from the headline**. Router calls are `role = "router"` and are
included (for `C1_inline` at their marginal cost; `cost_usd_list` on the
session record still holds the full turn). Escalation sessions are
`role = "escalation"` and included.

Every session runs with the config's `max_turns` (40 in the confirmatory
config). The per-task `max_turns` in `tasks.jsonl` is a human guess and is
not applied: the pilot's cheapest model needed 12-23 turns on tasks labelled
8-12, and a cap that binds only for some models would measure the cap, not
the model.

## Unit of measurement

One `SessionRecord` per agent session (many turns). One `DispatchOutcome` per
(task, policy, trial) with every session it caused, the grader checks, and
the files changed. Cost is list price from `pricing.toml` plus the CLI's own
reported cost where available.

## Grading (deterministic)

Each task ships a fixture repo, a visible checker the agent may run, and
hidden tests copied in only after the agent finishes. A task passes when:
hidden tests pass, visible tests still pass, and no file outside
`allowed_paths` changed. No LLM judge.

## Statistics

Paired design: every sampled task runs under every selected policy, same
trials. Intervals are 95% task-clustered bootstrap (2,000 draws; trials of
one task stay together). Non-inferiority on pass rate: the lower bound of
the paired difference `treatment − control` must exceed `−margin`. Savings:
the whole interval on `1 − cpt(treatment)/cpt(control)` must lie above zero.
Every verdict is one of `supported`, `not supported`, `inconclusive`.

Alongside the intervals the report gives, per comparison:

- `p_saving`: two-sided task-clustered permutation test (labels of all
  trials of a task swap together) on the log ratio of cost per completed
  task;
- `p_pass`: the same permutation test on the pass-rate difference;
- `p_noninf`: one-sided bootstrap p-value for "worse by at least the
  margin";
- `p_adj`: Holm-adjusted `p_saving` across the secondary hypotheses
  (H-D2..H-D7), which are exploratory. H-D1 is the only confirmatory test
  and is not adjusted.

The power note sizes the primary comparison from the *observed* discordance
(share of paired task-trials where the two policies disagree) with the
McNemar approximation; "inconclusive" at small n is the expected result, not
a null.

### Controls against the usual confounds

| Confound | Control |
|---|---|
| Clock-time / provider drift | `order = "randomized"`: a seeded randomized block design per (task, trial); sessions stay sequential |
| Model alias drift | every session records the resolved model id; `meta.json` records CLI versions and the harness git SHA |
| Task-set or config edits after registration | `taskset_sha256` over the whole task tree and the config hash in `meta.json`; the report lists every deviation from `[preregistration]` and downgrades the run to exploratory |
| Guessed difficulty labels | labels are measured from a calibration run (`dispatch-calibration`) and stored with their pass rates in `tasks.jsonl` |
| Brief-quality confound in routing | `C1_inline` routes on the parent's own brief-writing turn but the worker gets the same canned brief as `B` |
| Router overhead overstated | `C1_inline` bills only the marginal pick tokens; `C1` keeps the pessimistic full router call |
| Selective reporting | primary metric, margin, trials, ordering and policies fixed before the run; secondary tests Holm-adjusted and labelled exploratory |
| Silent failures | provider errors are graded as-is and counted (intention to treat) and the error rate is reported per policy |

## Safety and spend

Agents run with tools inside a throwaway sandbox copy of the fixture repo,
on the operator's own `claude` / `codex` login. Nothing runs without an
estimate and a budget; the budget is checked after every session.

### Codex track caveats

The Codex/ChatGPT replication (`exp05_dispatch_codex.toml`, with
`exp05_calibrate_codex.toml` and `exp05_smoke_paths_codex.toml`) runs the
same policies through `codex exec`, checked against codex-cli 0.154.0
(`CodexAgentProvider` in `src/model_routing/dispatch/agents.py` has the
details). Where it cannot match the Claude track, and what it does instead:

| Claude track | Codex track | Effect on the comparison |
|---|---|---|
| `--max-budget-usd` stops a session on spend | no equivalent (the `token_budget` feature is unreleased) | the budget is policed only **between** sessions; one runaway session can overshoot `--budget-usd` by up to its own cost. The wall clock (`timeout_s`, 1200 s) is the only hard stop inside a session |
| `--max-turns 40` counts model turns | the provider kills the session after more than 40 **tool calls** (one Codex turn can batch several) | the Codex cap binds no later than Claude's; capped sessions end with `error = "max_turns"` and are graded as-is |
| `--tools ""` removes every tool for router/classifier calls | read-only sandbox, shell tools disabled, and a one-line "answer from this conversation alone" notice appended to the prompt | a no-tools call cannot change files, but its prompt differs by that line and it may still *attempt* a tool call (visible in `tool_calls`) |
| `--resume --fork-session` | `codex exec fork` (new thread, parent untouched); `codex exec resume` for A / A_switch | equivalent. `resume`/`fork` take no `-s`/`-C`; the sandbox is passed as `-c sandbox_mode=...` (0.154.0 builds it from the current invocation, not the original session) |
| `total_cost_usd` reported | no dollar figure; list price from `pricing.toml` only | no cross-check against a vendor-reported cost |
| usage per session from the `result` event | `turn.completed` reports the **thread-cumulative** total, seeded from the parent on resume/fork | the provider subtracts the parent's totals (`raw.usage_baseline_known`); a timed-out, capped or failed session is billed from its rollout file under `$CODEX_HOME/sessions` (`raw.usage_source = "rollout"`), or at $0 if none exists (`"none"`) |
| `--setting-sources ""`, `--strict-mcp-config` | `--ignore-user-config --ignore-rules`, plugins/apps/memories/multi-agent/web search off, no network in the sandbox | skills installed under `~/.codex/skills` / `~/.agents/skills` are still listed in every session's context (no switch for it in 0.154.0), so Codex sessions carry a larger fixed prompt |
| effort: CLI default per alias | effort pinned to the catalog default (luna/terra medium, sol low) | `sol` already defaults to low, so the `opus_low` arm has no Codex counterpart and is omitted |

Every Codex failure mode (timeout, cap, non-zero exit, `turn.failed`, missing
binary) still returns a result with `error` set, and the task is graded on
whatever the agent left in the sandbox (intention to treat).

## Running

```bash
# No-spend cost estimate (states its token-profile assumptions explicitly).
make dispatch-estimate EXP=experiments/agentic/exp05_dispatch.toml

# Full run end to end with the fake agent provider - exercises every policy,
# the sandbox/grading/report plumbing, and produces a real summary.json/md,
# but spends nothing.
make dispatch-sim EXP=experiments/agentic/exp05_pilot.toml

# A small, cheap pilot to size variance and cost before the confirmatory run.
# Pilots do not test H-D1; run more trials/tasks for that.
make dispatch-run EXP=experiments/agentic/exp05_pilot.toml BUDGET=2.00

# Difficulty calibration: every task on every static candidate, then fold the
# measured pass rates into tasks.jsonl (WRITE=1 relabels).
make dispatch-run EXP=experiments/agentic/exp05_calibrate.toml BUDGET=80.00 TRIALS=3
make dispatch-calibration RUNS="results/exp05_calibrate/<stamp>" WRITE=1

# Smoke the paths the pilot never exercised on real models (A, A_switch,
# C1_inline, D escalation) before registering.
make dispatch-run EXP=experiments/agentic/exp05_smoke_paths.toml SAMPLE=2 BUDGET=4.00

# Freeze the design against the current task set (appends [preregistration]).
make dispatch-preregister EXP=experiments/agentic/exp05_dispatch.toml WRITE=1

# The pre-registered confirmatory run (at least B, C1_inline and the static
# baselines; see docs/experiments/preregistration-exp05.md for the budget table).
make dispatch-run EXP=experiments/agentic/exp05_dispatch.toml BUDGET=200.00 \
  POLICIES=B,C1_inline,static_haiku,static_sonnet

# (re)build summary.json/summary.md for an existing run directory.
make dispatch-report RUN=results/exp05_dispatch/20260922-120000

# White-paper Markdown draft (numbers filled, prose left as [TODO: author]);
# several RUNS are pooled. Never copies model output into the draft.
make dispatch-paper RUNS="results/exp05_dispatch/20260922-120000" \
  OUT=docs/experiments/findings/2026-09-30-exp05-paper-draft.md

# Scan local Claude Code transcripts for spawned task chips to grow the task set.
make harvest-chips
```

Equivalently, via the CLI directly:

```bash
model-routing dispatch-estimate experiments/agentic/exp05_dispatch.toml
model-routing dispatch-run experiments/agentic/exp05_dispatch.toml \
  --budget-usd 25.00 --sample 8 --trials 3 [--policies A,B,C1,D] [--fake] [--keep-sandboxes]
model-routing dispatch-report results/exp05_dispatch/<stamp>
model-routing dispatch-paper results/exp05_dispatch/<stamp> [more run dirs] [--out draft.md]
model-routing harvest-chips [--projects-dir ~/.claude/projects] [--out tasks/agentic/private/harvested.jsonl]
```

`dispatch-run` always prints the no-spend estimate first (calibrated from
observed sessions under `results/` when there are at least five for a
model and role, otherwise from stated assumptions), runs sequentially
(never in parallel - ordering is an experimental variable), stops cleanly and
marks the run `over_budget` if the budget is exceeded, and prints the H-D1
headline sentence at the end. `--fake` uses a deterministic no-spend agent
provider so the whole pipeline (sandboxing, grading, pricing, budget, report)
can be exercised without spending; `--keep-sandboxes` leaves the sandbox
copies on disk under `<run_dir>/sandboxes/` for inspection instead of deleting
them after grading.
