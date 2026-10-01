---
title: Local CI-equivalent verify suite
terse: Add a pnpm verify entry point that runs every CI check locally with a clear summary, skips semgrep loudly when absent, and wire it into the pre-push hook without breaking its design.
repo: trailhead-ci
parent: harvested
allowed: ["scripts/*", "package.json", "CLAUDE.md", "docs/*", "cli/*"]
category: feature
tags: [harvested, shell, ci, tooling]
stratum: A
max_turns: 40
visible_cmd: ["node", "--test"]
agent_bash: ["git:*", "bash:*", "node:*", "grep:*", "rg:*", "find:*", "chmod:*", "shellcheck:*"]
harvest_id: 611bfa17fe10029d
draw_position: 41
adaptations: "Repo, package and org renamed; absolute path replaced by the working directory; offline note added (no pnpm, database or network; shared workflow saved under gh-snapshot/; commit locally instead of push and PR; no wall-clock measurement possible). Fixture repo written for the task; the grader runs the repo's own verify command against stub pnpm/semgrep and a scratch git remote."
authorship: "Brief: harvested text (parent model wrote it). Fixture, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** The repo is the current working directory, on `main`. There is no network, no database, no `pnpm` and no `node_modules`: skip `pnpm agent:new` and the `db:migrate`/`db:verify` step, and you cannot run `pnpm verify` end to end here, so say what you could and could not measure rather than inventing a wall-clock figure. `node` is available (`node --test` runs the repo's `.mjs` tests). The shared workflow that `gh api ... ci.yml` would return is saved at `gh-snapshot/repos/Copperline/.github/contents/.github/workflows/ci.yml`. There is no remote: commit on a local branch and describe the PR body in your report instead of pushing or opening a PR.

Build a local verification suite that runs everything GitHub Actions runs, wired into the existing `pre-push` hook, in the `pathwise` repo (the current working directory). Read CLAUDE.md first — it is long and its rules override defaults.

## FIRST: create your own environment

    pnpm agent:new local-ci --from origin/main

`--from origin/main` is mandatory — the local `main` ref lags. Then `pnpm db:migrate && pnpm db:verify` in the worktree. Never take port 3000, never `pkill` anything. Another agent is running and owns `src/lib/career/notifications.ts`, `src/components/career/approval-card.tsx`, `src/lib/agents/skill-validator.ts` and the growth/feed notification copy — stay out of those.

## Why

This is a PRIVATE repo, so Actions minutes are metered. Measured over one day: **80 `pull_request`-triggered runs against 20 `push`-triggered runs.** The operator is the only contributor and intends to push straight to `main`, skipping PRs. He needs the same coverage locally, before the push, rather than after it.

## What CI actually runs

From `.github/workflows/ci.yml` (which delegates to `Copperline/.github/.github/workflows/ci.yml@main`) plus the repo-local jobs. Read both — fetch the shared one with `gh api repos/Copperline/.github/contents/.github/workflows/ci.yml --jq .content | base64 -d`. The jobs are:

| CI job | Command |
|---|---|
| Lint & format (Biome) | `pnpm check` |
| Type check | `pnpm exec tsc --noEmit` |
| Unit tests (Vitest) | `pnpm test` |
| Build | `pnpm build` |
| DB migration check | fails when `src/db/schema.ts` changed with no new file under `drizzle/` — shell logic lives in the shared workflow, replicate it |
| Security scan (Semgrep) | `semgrep` — see below |
| Migration sequence (repo-local) | `node scripts/check-migration-sequence.mjs` |
| lockfile / integrity | `scripts/check-lockfile.sh` |

Plus the e2e suite, which is local-only forever (ADR-0023) and already runs from `scripts/hooks/pre-push`.

## Build

**A single entry point** — suggest `pnpm verify` calling a new `scripts/verify.sh` — that runs every check above and reports a clear pass/fail summary naming which check failed and the exact command to reproduce it alone. Someone staring at a red result at 7am should not have to read the script.

**Semgrep is NOT installed on this machine** (I checked; `python3` is available at `/opt/homebrew/bin/python3`). CI pins `semgrep==1.172.0`. Do NOT make `pnpm verify` fail because semgrep is absent, and do NOT silently pretend it ran. Detect it, run it when present, and when absent print a loud, explicit line saying that one check was SKIPPED and how to install it. A suite that quietly covers 7 of 8 while claiming parity is worse than one that admits the gap — that is the same reasoning `feed_ingest`'s `unparsed` counter exists for.

**Wire it into `scripts/hooks/pre-push`.** Read that file's header first — its design is deliberate and you must preserve it:
- it SKIPS (exit 0) with a loud notice when the test environment is absent, and only BLOCKS on an actual failure — "a gate you must disable to do your job is a gate you stop reading";
- it already has a "is this push worth 70 seconds?" path-based early-out;
- `SKIP_E2E=1` is its documented escape hatch.

Keep all of that. Extend the same philosophy: the new checks should be fast enough to be tolerated on every push, and skip-with-notice rather than hard-fail when a prerequisite is genuinely missing.

**Speed matters or it will be bypassed.** `pnpm build` is the slow one. Run independent checks concurrently where it is safe (Biome, tsc, migration-sequence and lockfile are all independent); be careful about anything sharing the `.next` directory or the database. Report the measured wall-clock time for a full run in your PR body — that number decides whether this gets used.

**Avoid double work.** `.claude/settings.json`'s PreToolUse commit gate already runs `pnpm check && pnpm test` on every commit. Decide whether pre-push should re-run those or trust the commit gate, and justify your choice — a full re-run on every push may be the right call for a direct-to-main workflow, but say why.

## Explicitly NOT in scope

- **Do NOT change any workflow file, workflow trigger, or branch-protection setting.** That is the operator's decision and I am handling it separately. In particular do not remove the `push: branches: [main]` trigger — the plan is to KEEP CI on pushes to main as a backstop, precisely because a local gate can be bypassed with `--no-verify`.
- **Do NOT enable force pushes or touch branch protection via the API.** `allow_force_pushes` is currently `false` and should stay false.
- Do not add an e2e job to CI (ADR-0023, permanent).

## Docs

Add a short section to `docs/maintenance/e2e-suite.md` or a new runbook — your call which reads better — covering what `pnpm verify` runs, what it skips and why, how to install semgrep for full parity, and how to bypass in an emergency. Also add a line to CLAUDE.md's "Code Style" or "Testing" section, since it currently says only that `pnpm check` is Biome-only and `tsc` is a separate gate — `pnpm verify` is now the answer to "how do I check everything at once".

## Ground rules

- Biome only for the TS/JS you touch: `pnpm check:fix`, then `pnpm check && pnpm test`, and `pnpm exec tsc --noEmit`.
- Shell scripts in this repo are bash with `set -euo pipefail` — match `scripts/check-lockfile.sh` and `scripts/hooks/pre-push` in style and in comment density.
- Test what is testable: the shell orchestration is hard to unit-test, but the DB-migration-check logic is not. There is precedent — `scripts/check-migration-sequence.test.mjs`, and `cli/career.test.mjs` runs a CLI as a child process against a stub. Follow whichever fits.
- Never trigger anything that spends model allowance; do not run `pnpm dev` against the operator's database.
- Let the `pre-push` gate run on your own push — including your new checks, which is the real proof. Do NOT use `SKIP_E2E=1`.
- Branch, commit, open a PR with `gh`. No issue exists; describe the 80-vs-20 measurement in the body as the justification.

Report back: branch and PR URL; the exact list of checks `pnpm verify` runs and which it skips when; measured wall-clock time for a full run; your decision on re-running the commit-gate checks and why; how semgrep absence is surfaced; confirmation you changed no workflow or branch-protection setting; test/`tsc` results verbatim; and anything you deliberately did not do.
