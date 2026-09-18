# Project conventions

Python project scaffolded from `kornsour/python-template`.

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
