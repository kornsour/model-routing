# model-routing — common workflows (uv-managed env).
.DEFAULT_GOAL := help
PY := uv run

.PHONY: help setup test lint fmt fmt-check typecheck check clean smoke estimate run report dashboard lab \
	dispatch-estimate dispatch-run dispatch-sim dispatch-report dispatch-paper dispatch-calibration dispatch-preregister harvest-chips app \
	export backup restore backup-status backup-config

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Create the venv and install dev deps + pre-commit hook, from uv.lock
	uv sync --extra dev
	$(PY) pre-commit install || true

test: ## Run the test suite
	$(PY) -m pytest

lint: ## Lint with ruff
	$(PY) -m ruff check .

fmt: ## Auto-format and fix with ruff
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

fmt-check: ## Check formatting with ruff (no changes)
	$(PY) -m ruff format --check .

typecheck: ## Type-check with pyright
	$(PY) -m pyright

check: lint fmt-check typecheck test ## Run everything CI runs, locally

smoke: ## One trivial headless call per CLI; prints usage + cost (PROVIDER=claude_cli|codex_cli)
	$(PY) model-routing smoke --provider $(or $(PROVIDER),claude_cli)

estimate: ## Dry-run list-price estimate for an experiment (EXP=experiments/llm/exp01_baselines.toml)
	$(PY) model-routing estimate $(or $(EXP),experiments/llm/exp01_baselines.toml)

run: ## Run an experiment (EXP=..., LIMIT=n | SAMPLE=n, BUDGET=usd, TRIALS=n, ROUTERS=a,b, COOLDOWN=secs)
	$(PY) model-routing run $(or $(EXP),experiments/llm/exp01_baselines.toml) \
		$(if $(LIMIT),--limit $(LIMIT)) $(if $(SAMPLE),--sample $(SAMPLE)) \
		$(if $(BUDGET),--budget-usd $(BUDGET)) $(if $(TRIALS),--trials $(TRIALS)) \
		$(if $(ROUTERS),--routers $(ROUTERS)) $(if $(COOLDOWN),--cooldown-s $(COOLDOWN))

report: ## Rebuild summary.md/csv for a run dir (RUN=results/<exp>/<stamp>)
	$(PY) model-routing report $(RUN)

dashboard: ## Index results/ into results/index.sqlite and open results/dashboard.html
	$(PY) model-routing dashboard --open

clean: ## Remove caches
	rm -rf .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

lab: ## Serve the local experiment platform at http://127.0.0.1:8765
	$(PY) model-routing serve

dispatch-estimate: ## Dry-run list-price estimate for a dispatch experiment (EXP=experiments/agentic/exp05_dispatch.toml)
	$(PY) model-routing dispatch-estimate $(or $(EXP),experiments/agentic/exp05_dispatch.toml) \
		$(if $(SAMPLE),--sample $(SAMPLE)) $(if $(TRIALS),--trials $(TRIALS)) $(if $(POLICIES),--policies $(POLICIES))

dispatch-run: ## Run a dispatch experiment (EXP=..., BUDGET=usd required, SAMPLE=n, TRIALS=n, POLICIES=A,B,C1)
	$(PY) model-routing dispatch-run $(or $(EXP),experiments/agentic/exp05_dispatch.toml) \
		--budget-usd $(or $(BUDGET),1.00) \
		$(if $(SAMPLE),--sample $(SAMPLE)) $(if $(TRIALS),--trials $(TRIALS)) $(if $(POLICIES),--policies $(POLICIES))

dispatch-sim: ## Full fake dispatch run end to end, no spend (EXP=..., SAMPLE=n)
	$(PY) model-routing dispatch-run $(or $(EXP),experiments/agentic/exp05_dispatch.toml) \
		--fake --budget-usd 1000 $(if $(SAMPLE),--sample $(SAMPLE))

dispatch-report: ## Rebuild summary.json/md for a dispatch run dir (RUN=results/<exp>/<stamp>)
	$(PY) model-routing dispatch-report $(RUN)

dispatch-paper: ## Markdown white-paper draft from dispatch run dir(s) (RUNS="results/a [results/b]", OUT=path.md)
	$(PY) model-routing dispatch-paper $(RUNS) $(if $(OUT),--out $(OUT))

dispatch-calibration: ## Measured per-task pass rates by model from calibration run(s) (RUNS="results/a results/b", WRITE=1 relabels tasks.jsonl)
	$(PY) model-routing dispatch-calibration $(RUNS) $(if $(WRITE),--write)

dispatch-preregister: ## Print (WRITE=1: append) the [preregistration] table for a config (EXP=...)
	$(PY) model-routing dispatch-preregister $(or $(EXP),experiments/agentic/exp05_dispatch.toml) $(if $(WRITE),--write)

harvest-chips: ## Scan local Claude Code transcripts for spawned task chips -> tasks/agentic/private/harvested.jsonl
	$(PY) model-routing harvest-chips

app: ## Launch the dispatch routing lab as a desktop app (opens the browser)
	$(PY) model-routing serve --open --page dispatch

export: ## Zip a run into <experiment>__<stamp>.zip (RUN=results/<exp>/<stamp>, OUT=dir)
	$(PY) model-routing export $(RUN) $(if $(OUT),--out $(OUT))

backup: ## Back up run(s) to the configured backup dir (RUN=results/<exp>/<stamp> optional, TO=dir)
	$(PY) model-routing backup $(if $(RUN),--run $(RUN)) $(if $(TO),--to $(TO))

backup-status: ## Show per-run backup freshness
	$(PY) model-routing backup-status

backup-config: ## Show or change the backup directory / auto-backup (DIR=path, AUTO=on|off)
	$(PY) model-routing backup-config $(if $(DIR),--dir $(DIR)) $(if $(AUTO),--auto $(AUTO))

restore: ## Copy runs missing from results/ back in from a backup dir and reindex (DIR=backup dir)
	$(PY) model-routing restore $(DIR)
