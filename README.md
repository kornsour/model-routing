# model-routing

Experiment harness for model routing

Read [`docs/experiments/llm-routing.md`](docs/experiments/llm-routing.md) for
the hypotheses and how to read a result, and
[`docs/paradigms.md`](docs/paradigms.md) for the roadmap beyond LLMs.

## Quick start

```bash
make setup                                   # uv venv + dev deps + pre-commit
make check                                   # ruff + pyright + pytest (what CI runs)
make smoke                                   # one trivial Claude call; prints tokens + cost
make estimate EXP=experiments/llm/exp01_baselines.toml   # no spend
make run EXP=experiments/llm/exp01_baselines.toml LIMIT=5 BUDGET=0.50
make dashboard                               # index results/ -> SQLite, open the HTML dashboard
```

Requires the `claude` CLI logged in (Pro/Max) and, for cross-vendor
experiments, the `codex` CLI logged in (ChatGPT).

## Dispatch routing

`docs/experiments/dispatch-routing.md` covers a second, agentic question: does
it pay to choose the model *when work is handed off* (a spawned task chip, a
subagent), rather than always spawning on the parent's own model? Sessions run
with tools inside a throwaway sandbox copy of a fixture repo and are graded
deterministically (visible + hidden tests). Nothing spends without an estimate
and `--budget-usd`:

```bash
make dispatch-estimate EXP=experiments/agentic/exp05_dispatch.toml   # no spend
make dispatch-sim EXP=experiments/agentic/exp05_pilot.toml           # full run, fake provider, no spend
make dispatch-run EXP=experiments/agentic/exp05_dispatch.toml BUDGET=5.00
make dispatch-report RUN=results/exp05_dispatch/<stamp>
make harvest-chips                                                   # scan local transcripts for task chips
```

## Layout

```
src/model_routing/
  types.py        Task, Candidate, Usage, CallRecord, Outcome  (paradigm-agnostic)
  providers/      claude_cli, codex_cli, fake   (how a candidate is invoked + measured)
  routers/        static, oracle, heuristic, classifier, cascade
  graders.py      deterministic checks (exact, number, regex, json_fields, ...)
  pricing.py      list prices from data/pricing.toml -> cost from token usage
  runner.py       ordered execution, per-call records, budget guard
  report.py       cost per completed task, cache hit, router overhead, Pareto
  store.py        SQLite index over results/ (runs, outcomes, calls)
  findings.py     per-run verdicts on the hypotheses, with the numbers behind them
  dashboard.py    single-file HTML dashboard (run history, evidence, charts, drill-down)
  cli.py          model-routing smoke | estimate | run | report | dashboard
  dispatch/       agentic, dispatch-time routing (see docs/experiments/dispatch-routing.md):
                    types.py runner.py policies.py report.py agents.py tasks.py
                    sandbox.py grading.py harvest.py api.py
tasks/llm/        task sets (JSONL) + shared context documents
tasks/agentic/    fixture repos + briefs for dispatch experiments
experiments/llm/  one TOML per single-shot experiment
experiments/agentic/  one TOML per dispatch experiment
results/          run output (git-ignored); promote findings to docs/experiments/findings/
```

## Experiments

| Config               | Question                                                                                                 |
| -------------------- | -------------------------------------------------------------------------------------------------------- |
| `exp01_baselines`    | Cost per completed task for each single model, including the frontier model at low effort                |
| `exp02_routing`      | Oracle, heuristic, classifier, and cascade routers vs. those baselines, with cache fragmentation visible |
| `exp03_cache_order`  | Does interleaving requests across models change the cache picture?                                       |
| `exp04_cross_vendor` | The Codex harness floor and a cross-vendor cascade                                                       |
| `exp05_dispatch` (agentic) | Does dispatch-time routing (letting the parent pick the model when it spawns a task) lower cost per completed task? See `docs/experiments/dispatch-routing.md`. |
| `exp05_dispatch_codex` (agentic) | Same design, ChatGPT/Codex candidates |
| `exp05_pilot` (agentic) | Small, cheap pilot to size variance/cost before the confirmatory run |

## Data safety

`results/` (JSONL logs, `meta.json`, `summary.*`, `index.sqlite`) is
git-ignored and is the source of truth for every run; if this checkout lives
in a git worktree, deleting the worktree deletes it with nothing left behind.
Real (non-`--fake`) runs are auto-backed-up on finish — by default to a
detected Google Drive for desktop folder — with per-run manifests, a
standalone `report.html`, and a `.zip` export; see "Data safety" in
[`docs/experiments/platform.md`](docs/experiments/platform.md) for where
backups land and how to restore them:

```bash
make backup-config DIR="$HOME/Google Drive/model-routing-backups"  # or auto-detected
make backup                                  # back up every run now
make backup-status                           # per-run freshness
make export RUN=results/<experiment>/<stamp> # zip one run + report + README
make restore DIR=<backup dir>                # copy missing runs back in, reindex
```

## Conventions

`make check` is the CI gate. Dependencies are stdlib-only at runtime; dev
tools are pinned in `uv.lock`. See [`CLAUDE.md`](CLAUDE.md) and
[`docs/agent.md`](docs/agent.md) for agent and infrastructure rules.

## License

MIT — see [LICENSE](LICENSE).
