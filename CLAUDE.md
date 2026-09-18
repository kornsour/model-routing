# Project conventions

Python project scaffolded from `kornsour/python-template`. It is an experiment
harness for model-routing tradeoffs; see `README.md` and
`docs/experiments/llm-routing.md` before changing routers, providers, or the
report.

## Experiment harness rules

- **Spend is real.** LLM providers run `claude -p` / `codex exec` on the
  operator's personal login, metered at API rates. Never run an experiment
  without `model-routing estimate` first and `--budget-usd` on the run. Never
  ship the subscription path anywhere but this laptop.
- **Every call is recorded.** Providers must return normalized `Usage`
  (uncached input, cache read, cache write, output, reasoning) and the
  provider's own cost when it reports one; the runner prices every call from
  `src/model_routing/data/pricing.toml`. Add a price row before adding a model.
- **The headline metric is cost per completed task**, not cost per request.
  Router overhead calls are billed to the task (`role = "router"`).
- **Ordering is an experimental variable** (prompt caches are model-scoped
  and expire). Keep `order` explicit in configs; do not parallelize calls.
- **Graders are deterministic.** No LLM-as-judge unless a task set says so.
- `results/` is git-ignored. Promote findings to `docs/experiments/findings/`.

- **Env & deps:** `uv`. `make setup` runs `uv sync --extra dev`, installing
  exactly what `uv.lock` pins. Add runtime deps to `[project.dependencies]`;
  keep heavy/optional ones under `[project.optional-dependencies]` so CI stays
  light. After adding/changing a dependency, run `uv lock` and commit the
  updated lockfile (kornsour/gh-automation#18 tracks making CI itself enforce
  this with a `uv lock --check` step, once the reusable workflow adopts it).
- **Quality gate:** `make check` (ruff lint + ruff format + pyright + pytest) is
  exactly what CI enforces. Run it before pushing.
- **CI:** `.github/workflows/ci.yml` calls the reusable
  `kornsour/gh-automation/.github/workflows/python-ci.yml`. Don't inline CI logic
  here — change it upstream in `gh-automation` so every repo benefits.
- **Dependencies:** Dependabot opens grouped weekly PRs; patch/minor auto-merge
  when green. Review majors yourself.
- **`main` is protected:** merge via PR; the `ci / Lint, type-check & test` check
  must pass.

## Archive

[`archive/`](./archive/) holds historical/superseded documentation and
records. Treat its contents as past context only — never as current state,
and never as guidance for new work.

## Infrastructure as code

Read [`docs/agent.md`](./docs/agent.md) before adding cloud resources. This
repository owns deployable application infrastructure; the private
organization-level source of truth is recorded only in the derived project's
private `PROJECT_CONTEXT.md`. Use exact repository-and-environment-scoped
GitHub OIDC roles, keep account-specific values and secrets out of public docs,
tag resources, include an IaC plan/cost/rollback summary in the PR, and obtain
explicit authority before creating external or billable resources.
