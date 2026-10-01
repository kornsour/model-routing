---
title: Landing page headline rewrite
terse: Replace the landing page h1 and subhead with career-development framing, keep the alternative as a comment, and update the e2e assertion and literal duplicates.
repo: trailhead-web
parent: harvested
allowed: ["src/app/*", "e2e/*", "README.md"]
category: feature
tags: [harvested, copy, frontend, judgment]
stratum: A
max_turns: 40
visible_cmd: ["node", "--test"]
agent_bash: ["git:*", "node:*", "grep:*", "rg:*"]
harvest_id: d33a62e0561d2471
draw_position: 14
adaptations: "Product and repo renamed; offline note added (no node_modules or network: skip pnpm install and the pnpm gates; node --test runs the unit tests). Fixture repo written for the task, with the old headline duplicated in layout metadata and README."
authorship: "Brief: harvested text (parent model wrote it). Fixture, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** The worktree is the current working directory. It has no `node_modules` and there is no network, so skip `pnpm install` and the `pnpm` gates (Biome, `tsc`, Vitest); `node --test` runs the repo's unit tests. Committing on the current branch is fine.

Small, self-contained copy change to the Pathwise marketing landing page in the `trailhead` repo.

FIRST: `pnpm install --prefer-offline` — your worktree has no node_modules and cannot run a gate until it does.

## The change

`src/app/page.tsx` line ~46 currently has this `<h1>`:

    Run your job search like a portfolio, not a lottery.

The operator dislikes the "not a lottery" half, and wants the product framed as an overarching **career development / career path** tool rather than a job-search tool specifically — the app genuinely does more than search (skill gaps, a learning plan, project proposals, warm paths through the contact book, growth tracking).

**Replace the h1 with exactly:**

    Automate the busywork of building a career.

**Directly above it, leave a commented-out alternative** the operator explicitly asked to keep on hand in case he wants to switch:

    Source roles. Score fit. Close skill gaps.

Write that as a normal JSX comment with a one-line note saying it is a kept alternative headline, not dead code to be cleaned up — otherwise a future tidy-up pass deletes it. Keep it brief; do not write a paragraph.

## Also update the subhead to match

The `<p>` under the h1 currently reads:

> Pathwise sources roles, scores fit, tailors your materials, and drafts outreach — autonomously where you want it, held for review where it matters. A persistent context library keeps every agent consistent, and nothing is sent, submitted, or saved without passing your desk.

Rework it so it no longer reads as job-search-only, and so it names the growth/development half of the product too. The operator asked to **be succinct and focus on the features**. A good target is roughly:

> Sources roles, scores fit against your real experience, tracks the skills worth learning, and drafts outreach in your voice — nothing sent without passing your desk.

Use your judgement on the exact wording, but: keep it shorter than the current one, keep it feature-forward, and **keep the review-gate promise** ("nothing sent without passing your desk" or equivalent). That last clause is not marketing garnish — it is a true and load-bearing claim about how the autonomy gate works (see CLAUDE.md on `requestAction()` and `OUTBOUND_SENDING`), and the page must not overstate autonomy in a way the product does not actually do.

## Do not overstate anything

Every claim on this page must be true of the shipped product. Do not add a feature to the copy that does not exist. If you find yourself wanting to claim something, check it in the code first. In particular: nothing on `/messages` sends, email delivery is off by default, and the outbound kill switch is off by default — do not write copy implying the app sends things on its own.

## Other places the old string may live

`e2e/home.spec.ts:19` asserts the heading by exact text:

    page.getByRole("heading", { name: "Run your job search like a portfolio, not a lottery." })

That MUST be updated in the same change or the e2e suite breaks. **Search the whole repo** for other copies of the old headline and for other job-search-only framing that should move with it — page metadata / `<title>` / OpenGraph description, `README.md`, `src/app/layout.tsx`, the legal or content config, anywhere. Report what you found and what you chose to change or leave. Do not go on a rewriting spree: change the headline, its subhead, the e2e assertion, and anything that is a literal duplicate of the old headline string. Leave broader marketing prose alone unless it repeats the old line verbatim.

## Gates

`pnpm check:fix`, then `pnpm check`, `pnpm exec tsc --noEmit` (Biome is NOT a type check), and `pnpm test`.

Do NOT run `pnpm e2e` — it is expensive, it serializes across every agent worktree via a lock, and other agents are active on this machine right now. Instead, verify your e2e edit by reading the spec and confirming the string matches your new h1 exactly, character for character, and say in your report that you verified it by inspection rather than by running the suite.

## Constraints

- You are in a git worktree; work only there, never `cd` to the repo root.
- Never take port 3000 and never run a dev server in the main checkout — the operator owns both all day against the real database. Never `pkill -f` anything.
- A sibling agent is concurrently building the Electron desktop shell. **Do not touch `desktop/`, `next.config.ts`, `package.json`, `pnpm-workspace.yaml`, or anything under `docs/adr/`.**
- Commit to your branch with a conventional-commit message ending with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Do NOT push to `main` and do NOT open a PR — the parent session integrates.

Report back: the exact final text of the h1, the commented alternative, and the subhead; every file you changed; every other occurrence of the old framing you found and what you did about it; and confirmation that the e2e assertion string matches the new h1 exactly.
