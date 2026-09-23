# Dispatch-time routing: does choosing the model when work is handed off save money?

## The claim under test

Assistants already split work: a parent session spawns a separate task (a
"task chip", a subagent, a background job) with a self-contained brief. The
spawner has full context and is already writing the brief, so asking it to
also pick the model is nearly free. A fresh session starts with a cold cache
whatever model runs it, so routing there does not fragment a cache, and there
is no mid-session model switch to degrade output.

**Primary hypothesis (H-D1).** Spawning with the model the parent recommends
(policy `C1`) has a lower cost per completed task than spawning with the
parent's own model (policy `B`), with a pass rate no more than the
non-inferiority margin (default 5 points) worse.

This is pre-registered: the metric, margin, policies, task set version and
trial count are fixed in `experiments/agentic/exp05_dispatch.toml` before the
confirmatory run. Pilot runs size variance and cost; they do not test H-D1.

## Secondary hypotheses

| # | Hypothesis | Comparison |
|---|---|---|
| H-D2 | Doing the task inside the parent session costs more per completed task than spawning with a brief, because every turn re-reads the parent's context. | `A` vs `B` |
| H-D3 | Switching model mid-session costs more than staying (cache rewrite) and passes less often. | `A_switch` vs `A` |
| H-D4 | A cheap-first cascade that escalates only when the checker fails beats a single routed pick when a real checker (tests) exists. | `D` vs `C1` |
| H-D5 | Parent-recommended routing beats a context-free router (classifier/heuristic on the brief alone) at lower router overhead. | `C1` vs `C2` |
| H-D6 | Brief quality matters as much as model choice: the cheap model with the full brief beats it with a terse brief by more than the cheap-vs-parent model gap. | `static_cheap` vs `static_cheap_terse` |
| H-D7 | An oracle (cheapest model that passed, in hindsight) bounds the saving; deployable policies recover part of it. | `oracle` (computed, not run) |

## Policies

| Policy | What happens | Parent session needed |
|---|---|---|
| `A` | Resume the seeded parent session; do the task there on the parent model | yes |
| `A_switch` | Resume the seeded parent session but with `switch_to` model | yes |
| `B` | Fresh session, parent model, full brief | no |
| `C1` | Resume parent (forked) and ask it for `{model, effort, reason}` from the menu (router call), then fresh session on that pick | yes |
| `C2` | Classifier/heuristic on the brief alone picks the model, then fresh session | no |
| `D` | Fresh session on the cheapest model; run the visible checker; on failure, escalate to the next model in `chain` with the failure log | no |
| `static:<cand>` | Fresh session on a fixed candidate (also feeds the oracle) | no |
| `oracle` | Computed in the report from `static:*` outcomes | — |

Seeding a parent session (loading `parent_context`) is billed with
`role = "setup"`. It is a sunk cost in reality, so it is reported but
**excluded from the headline**. Router calls are `role = "router"` and are
included. Escalation sessions are `role = "escalation"` and included.

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
trials. Intervals are 95% task-clustered bootstrap (trials of one task stay
together). Non-inferiority on pass rate: the lower bound of the paired
difference `C1 − B` must exceed `−margin`. Savings: the upper bound of the
paired difference in cost per completed task must be below zero. Every
verdict is one of `supported`, `not supported`, `inconclusive`.

## Safety and spend

Agents run with tools inside a throwaway sandbox copy of the fixture repo,
on the operator's own `claude` / `codex` login. Nothing runs without an
estimate and a budget; the budget is checked after every session.

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

# The pre-registered confirmatory run.
make dispatch-run EXP=experiments/agentic/exp05_dispatch.toml BUDGET=25.00 \
  SAMPLE=8 TRIALS=3

# (re)build summary.json/summary.md for an existing run directory.
make dispatch-report RUN=results/exp05_dispatch/20260922-120000

# Scan local Claude Code transcripts for spawned task chips to grow the task set.
make harvest-chips
```

Equivalently, via the CLI directly:

```bash
model-routing dispatch-estimate experiments/agentic/exp05_dispatch.toml
model-routing dispatch-run experiments/agentic/exp05_dispatch.toml \
  --budget-usd 25.00 --sample 8 --trials 3 [--policies A,B,C1,D] [--fake] [--keep-sandboxes]
model-routing dispatch-report results/exp05_dispatch/<stamp>
model-routing harvest-chips [--projects-dir ~/.claude/projects] [--out tasks/agentic/private/harvested.jsonl]
```

`dispatch-run` always prints the no-spend estimate first, runs sequentially
(never in parallel - ordering is an experimental variable), stops cleanly and
marks the run `over_budget` if the budget is exceeded, and prints the H-D1
headline sentence at the end. `--fake` uses a deterministic no-spend agent
provider so the whole pipeline (sandboxing, grading, pricing, budget, report)
can be exercised without spending; `--keep-sandboxes` leaves the sandbox
copies on disk under `<run_dir>/sandboxes/` for inspection instead of deleting
them after grading.
