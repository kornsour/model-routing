# model-routing — common workflows (uv-managed env).
.DEFAULT_GOAL := help
PY := uv run

.PHONY: help setup test lint fmt fmt-check typecheck check clean smoke estimate run report dashboard

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
