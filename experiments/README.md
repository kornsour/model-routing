# Experiments

One TOML per experiment; `model-routing run <file>` executes it and writes
`results/<name>/<timestamp>/` with `calls.jsonl` (every model call),
`outcomes.jsonl` (every task verdict), `meta.json`, a copy of the config, and
`summary.md`/`summary.csv`.

| File | Question |
|---|---|
| `llm/exp01_baselines.toml` | What does each single model cost per completed task, including the frontier model at low effort? |
| `llm/exp02_routing.toml` | Do oracle / heuristic / classifier / cascade routers beat the baselines on cost per completed task once overhead, retries, and cache fragmentation are counted? |
| `llm/exp03_cache_order.toml` | Does interleaving requests across models (as mixed traffic does) change the cache picture? |
| `llm/exp04_cross_vendor.toml` | What does the Codex harness floor do to a "cheap" OpenAI tier, and what does a cross-vendor cascade cost? |

Always `model-routing estimate <file>` first; it prints a list-price estimate
without spending anything. Then `run` with `--limit` and `--budget-usd`.

## Interactive experiment platform

Use `make lab` to configure, estimate, save, and launch same-vendor adoption
or routing-design experiments in a local UI. See
[platform design and experiment review](../docs/experiments/platform.md) for
quality gates, current capabilities, and the architecture/training roadmap.
