---
title: Fix fail-open cron auth
terse: Make the cron routes in packlight, cohort and echoform refuse requests when the shared secret is unset, following binwise's fail-closed helper.
repo: cron-fleet
parent: harvested
allowed: ["Copperline/*", "ellisport/*"]
category: bugfix
tags: [harvested, security, multi-repo, typescript]
stratum: A
max_turns: 40
visible_cmd: ["node", "--test"]
agent_bash: ["git:*", "node:*", "grep:*", "rg:*", "find:*"]
harvest_id: fb718d248158f73f
draw_position: 33
adaptations: "Org, personal account and repos renamed; absolute paths replaced by paths under the working directory; scratch brief written as a fixture file; offline note added (no Vercel CLI, no pnpm, node --test runs each repo's tests). Fixture repos written for the task: env access is a plain getter module and the database, job and storage clients are recording stubs; one manual-trigger route carries its own copy of the fail-open check instead of the shared helper."
authorship: "Brief: harvested text (parent model wrote it). Fixture, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** All four repositories are checked out under the current working directory (`Copperline/packlight`, `Copperline/cohort`, `Copperline/binwise`, `ellisport/echoform`). There is no network, no `vercel` CLI and no `node_modules`; each repo's tests run with `node --test` (Node 24 runs the `.ts` files directly), and `node --test` at the top level runs all of them.

SCRATCH=./scratch

Read `$SCRATCH/AWS-BRIEF-V2.md` for context on the wider effort, but your task is self-contained and in DIFFERENT repositories from the other agents. You will not collide with them.

TASK: fix a fail-open authorization defect in two production cron routes.

**The defect.** Both routes skip their authorization check entirely when the shared secret environment variable is unset, rather than refusing the request.

1. `Copperline/packlight/src/app/api/cron/purge/route.ts`
   The `GET` handler wraps its check in `if (env.CRON_SECRET) { ... }`. With `CRON_SECRET` unset there is no check at all, and the route hard-deletes rows from `item` and `trip` older than 30 days.

2. `Copperline/cohort/src/app/api/cron/daily/route.ts`
   `authorized()` computes `secrets = [env.AI_TICK_SECRET, env.CRON_SECRET].filter(Boolean)` then `if (secrets.length === 0) return true;` — an explicit fail-open. `CRON_SECRET` is `.optional()` in `src/env.ts` around line 29. The route drains billable AI jobs and, on Sunday and Monday, sends owner-digest and voice-of-customer emails to real users.

**The correct pattern** is already in `Copperline/binwise/src/app/api/cron/purge/route.ts`, which fails closed: a missing secret OR a mismatched header both yield 401. Follow that repo's approach so the three stay consistent.

**Also check** `ellisport/echoform/src/app/api/cron/retention/route.ts` (find the actual path) for the same pattern and fix it if present. Check whether `cohort` has sibling cron routes with the same helper — the file header mentions `/api/ai/tick`, `/api/cron/voc-digest`, and `/api/cron/owner-digest` as manual-trigger routes; if they share the fail-open `authorized()` helper, they have the same defect and should be fixed too.

**Steps:**

1. Before changing code, determine whether these secrets are actually SET in Vercel production for each project — that decides whether this is a live exposure or a latent one. Use the `vercel` CLI if it is authenticated (`vercel env ls` shows names without values). Check presence only; never print or log a secret value. If the CLI is not authenticated, say so and move on — do not attempt to authenticate. Report which case each project is in.

2. Fix each route to fail closed.

3. Consider whether the env schema should REQUIRE `CRON_SECRET` rather than mark it `.optional()`, so a missing secret fails at build or boot instead of silently disabling authorization at request time. Weigh this against local development and CI, where the variable may legitimately be absent — a schema change that breaks `next build` in CI is a bad trade. Make a recommendation and implement it only if it is clearly safe; otherwise explain why not.

4. Add or extend tests covering the fail-closed behavior: a request with no secret configured must be rejected, and a request with a wrong bearer token must be rejected. Follow each repo's existing test conventions — check for `vitest` and existing route tests before inventing a pattern.

5. Run each repo's own checks and make them pass. Look at `package.json` scripts and CLAUDE.md; typically some of `pnpm check`, `pnpm lint`, `pnpm test`, `pnpm verify`. Do NOT run `pnpm build` if it triggers database migrations (`cohort` and others run `db:deploy` in `build`) — that would touch a real database. Report the exact commands you ran and their results.

6. Do NOT commit, push, or open a PR. Leave every change in the working tree of each repo and report what you touched, file by file.

If a repo turns out not to be cloned locally, say so rather than guessing at its contents. If a fix is not safe to make without a decision the owner must take, implement what is safe and describe the rest.

When done, report per repo: whether the exposure was live or latent, exactly which files you changed, which checks you ran and their output, and anything you deliberately left alone.
