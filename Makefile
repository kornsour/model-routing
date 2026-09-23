# model-routing — common workflows (uv-managed env).
.DEFAULT_GOAL := help
PY := uv run

.PHONY: help setup test lint fmt fmt-check typecheck check clean smoke estimate run report dashboard lab \
	dispatch-estimate dispatch-run dispatch-sim dispatch-report harvest-chips

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

harvest-chips: ## Scan local Claude Code transcripts for spawned task chips -> tasks/agentic/private/harvested.jsonl
	$(PY) model-routing harvest-chips
