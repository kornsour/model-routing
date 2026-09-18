# Python Template

A batteries-included starting point for Python projects: **uv + hatchling**
packaging, **ruff** (lint + format), **pyright** type-checking, **pytest**,
**pre-commit**, and cost-savvy **centralized CI + Dependabot** — wired up from
the first commit.

> Click **“Use this template”** on GitHub to start a new repo from it, then run
> the steps below.

## Quick start

```bash
make setup      # create the venv, install dev deps, install the pre-commit hook
make check      # everything CI runs, locally: ruff check + ruff format --check + pyright + pytest
```

Then replace `src/python_template/` with your own package (update `name` under
`[project]` and the package path under `[tool.hatch.build.targets.wheel]` in
`pyproject.toml`, plus the import in `tests/`).

For agent and cloud/IaC boundaries, read [`docs/agent.md`](./docs/agent.md) and
[`CLAUDE.md`](./CLAUDE.md).

| Command | Does |
|---|---|
| `make setup` | venv + dev deps + pre-commit hook, from `uv.lock` |
| `make test` | pytest |
| `make lint` | ruff check |
| `make fmt` | ruff auto-fix + format |
| `make fmt-check` | ruff format --check |
| `make typecheck` | pyright |
| `make check` | lint + fmt-check + typecheck + test |
| `uv lock` | re-resolve `uv.lock` after changing a dependency — commit the result |

## What's included

- **Packaging** — `pyproject.toml` (PEP 621), `uv` for envs, `hatchling` build backend, `src/` layout.
- **Quality** — ruff (lint + format), pyright (basic, with `reportMissingImports`
  suppressed — see `[tool.pyright]` in `pyproject.toml`), pytest, pre-commit hooks.
- **CI** — `.github/workflows/ci.yml` calls the shared reusable workflow in
  [`kornsour/gh-automation`](https://github.com/kornsour/gh-automation).
- **Dependabot** — grouped weekly `pip` + `github-actions` updates with patch/minor auto-merge.
- **Pre-commit autoupdate** — `.github/workflows/pre-commit-autoupdate.yml` runs
  `pre-commit autoupdate` monthly and opens a PR, so pinned hook revs (notably
  `ruff-pre-commit`) keep tracking the ruff version CI installs.
- **Branch protection** — a repository ruleset requiring the CI check on `main`.

## Cost-conscious CI by design

Actions minutes are the scarce resource, so the setup minimizes them:

- **Public repo → unlimited free minutes.** Private repos draw down the billed
  quota; keeping the template public means CI is free.
- **One CI job, not four.** ruff, pyright, and pytest run in a single job — one
  runner spin-up and one dependency install per run, instead of a job-per-check
  fan-out.
- **`concurrency: cancel-in-progress`.** Pushing a new commit cancels the
  superseded run rather than letting both finish.
- **Dev extras only in CI.** Heavy runtime frameworks (torch/jax/…) live behind
  optional extras and never download during CI.
- **Dependabot grouping.** Minor/patch bumps arrive as one grouped PR per week
  (one CI run) and auto-merge once checks pass; majors come individually.
- **Self-hosted runner toggle.** Set the repo/org variable
  `USE_SELF_HOSTED_RUNNER=true` to route CI to a self-hosted runner (zero billed
  minutes); unset, it uses `ubuntu-latest`. **Private repos only** — a public
  caller always gets a GitHub-hosted runner regardless of this variable,
  because a pull request from a fork could otherwise execute arbitrary code on
  a self-hosted runner. Since this template (and anything generated from it by
  default) is public, the toggle has no effect unless the repo is private.

## Archive

[`archive/`](./archive/) holds historical/superseded documentation and
records. Its contents reflect past decisions or state, not the current
project — do not use it to understand how things work today or to guide new
work.

## License

MIT — see [LICENSE](LICENSE).
