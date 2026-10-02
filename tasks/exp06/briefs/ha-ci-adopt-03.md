---
title: Migrate crossfade and smallco to the org reusable CI
terse: Convert crossfade's and smallco's inline CI to thin caller stubs of the org's reusable workflow and report the ruleset edits the check-name change needs.
repo: ci-adopt
parent: harvested
allowed: ["Copperline/crossfade/*", "Copperline/smallco/*", "REPORT.md"]
category: config
tags: [harvested, ci, multi-repo, yaml]
stratum: A
max_turns: 40
visible_cmd: ["python3", "tools/check-workflows.py"]
agent_bash: ["git:*", "grep:*", "rg:*", "find:*", "jq:*"]
harvest_id: 5d653634f6dfa8c8
draw_position: 4
adaptations: "Org and repos renamed; scratchpad clone path dropped; offline note added (repos pre-cloned, gh api responses saved under gh-snapshot/, no push or PRs, report written to REPORT.md ending in a json block for grading). Fixture repos and API snapshots written for the task."
authorship: "Brief: harvested text (parent model wrote it). Fixture, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** There is no network and no `gh`. Both repos are already cloned under the current working directory (`Copperline/crossfade`, `Copperline/smallco`, with `Copperline/packlight` as the reference stub and `Copperline/mise` belonging to the other agent), so skip the clone step. Every `gh api` response this brief names is saved under `gh-snapshot/` (its README maps commands to files). Do not try to push or open PRs: leave the stubs in the working trees. Write your report to `REPORT.md` at the top of the working directory (that file is what gets read) and end it with a fenced `json` block of exactly this shape: `{"repos": {"crossfade": {"ruleset_id": <id>, "checks_before": [...], "checks_after": [...]}, "smallco": {...}}, "property_ruleset_satisfied": {"crossfade": true | false, "smallco": true | false}}`, where `checks_after` is every check name the new stub will emit. `python3 tools/check-workflows.py` parses the workflow files.

Migrate TWO repos off their inline CI onto the org's shared reusable workflow. **Do this work YOURSELF — do NOT spawn sub-agents.** Verify your own work by re-reading from GitHub at the end.

TOUCH ONLY: `crossfade` and `smallco`. Another agent is concurrently migrating `mise` — stay out of it.

`gh` is authenticated. Clone each into the scratchpad.

## Goal
The org centralizes CI in `Copperline/.github-private/.github/workflows/ci.yml`. These two still inline their own jobs. Convert each `.github/workflows/ci.yml` to a thin caller stub.

## Current state (verified from live runs)
- `crossfade` emits check names: `Unit tests`, `Lint`, `Build`. Three inline jobs, Node 22, runs `pnpm lint` (NOT Biome's `pnpm check`). No typecheck job. Stack is TypeScript + Rust/Tauri (`src-tauri/Cargo.toml`) — the Rust side is not currently built in CI; do not add it.
- `smallco` emits a single check named `ci`. One inline job: checkout → pnpm → `pnpm typecheck` → `pnpm test` → `pnpm build`. No lint step. pnpm 9.15.0 (oldest in the org), Node 22.

## The shared workflow's inputs
Read it first for the authoritative list:
`gh api "/repos/Copperline/.github-private/contents/.github/workflows/ci.yml" -H "Accept: application/vnd.github.raw"`
It accepts (verify against the file): `migration-check`, `node-version`, `security-scan`, `run-lint`, `run-typecheck`, `run-build`, `lint-command`, `typecheck-command`, `test-command`, `orm`, `generate-client`, `prisma-schema-path`, `postgres-service`.
Its job names are `Lint & format (Biome)`, `Type check`, `Unit tests (Vitest)`, `Build`, plus conditional `DB migration check` and `Security scan (Semgrep)`.
`packlight`'s `.github/workflows/ci.yml` is the reference caller stub shape.

Map each repo onto those inputs. Use caller job id `ci` (matching every other repo), which yields check names like `ci / Type check`. Where a repo genuinely lacks a capability (crossfade has no typecheck; smallco has no lint), use the `run-*: false` toggles rather than inventing config — and say so in the PR body.

## THE CRITICAL RISK — read carefully
Check names WILL change (`Lint` → `ci / Lint & format (Biome)`, `ci` → several `ci / *`). Org rulesets require status checks BY NAME. If the ruleset still requires the old name, **every PR in that repo blocks forever** on a check that no longer exists.

Before changing anything, read the current required checks:
`gh api /orgs/Copperline/rulesets` then fetch the `crossfade` ruleset (id 21612243) and `smallco` ruleset (id 21612244). Also note an org-wide ruleset `Required checks: TypeScript apps (by property)` (id 22285519) targets repos with custom properties `stack=typescript` AND `ci-managed=true` and requires: `ci / Build`, `ci / Lint & format (Biome)`, `ci / Security scan (Semgrep)`, `ci / Type check`, `ci / Unit tests (Vitest)`, `lockfile / integrity`.

**Do NOT edit any ruleset yourself.** Produce an explicit BEFORE→AFTER mapping per repo and report exactly which ruleset edits are needed. The orchestrator applies them. Note in your report whether the repo will emit all six checks that property ruleset wants — `crossfade` and `smallco` currently have `stack=mixed`, not `typescript`, so that ruleset does not target them today; say clearly whether their post-migration check set would satisfy it if it ever did.

Also: neither repo currently has a `lockfile.yml`. `smallco` does; `crossfade` does not. Check and report — do not add one unless it is trivially the same stub every other repo uses (`lockfile-guard.yml`).

## Constraints
- Pin `uses:` to `.github-private` main — resolve with `gh api /repos/Copperline/.github-private/commits/main --jq .sha`. 40-char SHA + trailing `# main` (org enforces `sha_pinning_required: true`).
- **Never use `secrets: inherit`** — the org's Semgrep rule treats it as a blocking ERROR-severity finding.
- Caller stubs must contain NO `runs-on:` and no job logic.
- Do NOT push to `main`. Branch `ci/adopt-org-reusable-ci`, one PR per repo.
- Hosted minutes are billing-blocked so PR CI is partly unreliable; validate YAML locally with `python3 -c "import yaml; yaml.safe_load(open(...))"`. Checks named `actionlint` or `auto-merge / *` failing is expected and not blocking.
- Do NOT merge these PRs — the check-name change needs a coordinated ruleset edit first. Leave them open and report.

Commit messages end with:
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
PR bodies end with:
🤖 Generated with [Claude Code](https://claude.com/claude-code)

REPORT: the two PR URLs, the exact inputs used per repo with justification, a full BEFORE→AFTER check-name mapping, the precise ruleset edits required, anything the shared workflow could not express, and confirmation neither stub uses `secrets: inherit` or `runs-on:`.
