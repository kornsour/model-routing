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
tasks/llm/        task sets (JSONL) + shared context documents
experiments/llm/  one TOML per experiment
results/          run output (git-ignored); promote findings to docs/experiments/findings/
```

## Experiments

| Config               | Question                                                                                                 |
| -------------------- | -------------------------------------------------------------------------------------------------------- |
| `exp01_baselines`    | Cost per completed task for each single model, including the frontier model at low effort                |
| `exp02_routing`      | Oracle, heuristic, classifier, and cascade routers vs. those baselines, with cache fragmentation visible |
| `exp03_cache_order`  | Does interleaving requests across models change the cache picture?                                       |
| `exp04_cross_vendor` | The Codex harness floor and a cross-vendor cascade                                                       |

## Conventions

`make check` is the CI gate. Dependencies are stdlib-only at runtime; dev
tools are pinned in `uv.lock`. See [`CLAUDE.md`](CLAUDE.md) and
[`docs/agent.md`](docs/agent.md) for agent and infrastructure rules.

## License

MIT — see [LICENSE](LICENSE).
