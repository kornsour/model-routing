---
title: Audit mise feature claims
terse: Verify five portfolio feature claims against the mise monorepo and judge each IMPLEMENTED, PARTIAL or ABSENT with evidence.
repo: mise-monorepo
parent: harvested
allowed: ["REPORT.md"]
category: investigation
tags: [harvested, read-only, audit, typescript]
stratum: A
max_turns: 40
visible_cmd: ["git", "status", "--short"]
agent_bash: ["git:*", "grep:*", "rg:*", "find:*", "wc:*", "head:*", "tail:*"]
harvest_id: db23a1ff18c2d7c3
draw_position: 7
adaptations: "Repo renamed; absolute path replaced by the working directory; offline note added (findings also written to REPORT.md ending in a json block for grading). Fixture monorepo written for the task; it has a single commit, so the git-activity question has little to report."
authorship: "Brief: harvested text (parent model wrote it). Fixture, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** The repo is the current working directory; there is no network and no `node_modules`. Besides returning your findings as your final message, write them to `REPORT.md` at the repo root (the one file you may create; it is what gets read) and end it with a fenced `json` block of exactly this shape: `{"claims": {"recipe_discovery": V, "weekly_planner": V, "grocery_lists": V, "store_integration": V, "subscription_billing": V}, "decorative_recipe_filters": [filter names that do not reach the query], "store_real_provider_api": true | false, "ai_chef_entitlement_enforced_server_side": true | false}` with each V one of `"IMPLEMENTED"`, `"PARTIAL"`, `"ABSENT"`.

READ-ONLY CODE AUDIT. Do not modify, create, or delete any file. Do not run a dev server, do not run `pnpm dev`, do not run Playwright/e2e, do not run `pnpm install`, do not kill processes. You MAY read files, grep, and run `git log`/`git show`. Use absolute paths.

Repo: the current working directory (pnpm monorepo: apps/web, apps/mobile, packages/core with Prisma schema at packages/core/prisma/schema.prisma).

A portfolio site publicly claims, verbatim: "A full meal-planning and grocery SaaS: recipe discovery, weekly planner, auto-generated grocery lists, grocery-store integration, and subscription billing." Tech listed: Next.js, Prisma, Postgres, Stripe.

Verify each of these FIVE feature claims against the actual code, end to end. For each, judge IMPLEMENTED / PARTIAL / ABSENT and cite absolute file paths with line references where useful.

1. RECIPE DISCOVERY — is there a browse/search/filter UI at apps/web/app/recipes, backed by real queries against Prisma models? Are filters (cuisine, diet, time) actually wired to the query, or decorative?

2. WEEKLY PLANNER — apps/web/app/planner and apps/web/app/plans. Is there a real week grid persisting meal assignments to DB models? Check the Prisma models and the server actions in apps/web/app/actions.

3. AUTO-GENERATED GROCERY LISTS — apps/web/app/grocery-list. Does it actually derive from the planner's meals (ingredient aggregation/unit consolidation), or is it a manually-entered list? Find the aggregation function and read it.

4. GROCERY-STORE INTEGRATION — this is the one most likely overstated. There is a directory apps/web/lib/grocery-adapters and a route apps/web/app/send-to-store. Read EVERY file in both. Determine precisely: is there a real integration with an actual grocery provider (Kroger / Instacart / Walmart / Amazon Fresh API — real HTTP calls, OAuth, cart creation, cart handoff), or is it (a) export/print/copy-to-clipboard, (b) a deep link to a store's search URL, (c) a mock/stub adapter with no live credentials, or (d) provider adapters behind an unset env flag? Check .env.example for provider credentials and check whether any adapter makes a real outbound fetch to a provider API. Quote the decisive code. Also check whether the UI is reachable and what it tells the user.

5. SUBSCRIPTION BILLING — is Stripe genuinely wired? Look for: Stripe product/price config, a checkout session creation path, a webhook handler (search apps/web/app/api for stripe webhook), a subscription/entitlement table in the Prisma schema, and — critically — whether entitlement is actually ENFORCED server-side on gated features (the landing page mentions "Pro Required" for an AI Chef Assistant). Find the enforcement check and the paths that call it. Note whether it's live-mode-capable or test-only scaffolding.

Also report: does apps/web/app/ai (AI features) exist and work; anything else notable.

Additionally note briefly: recent commit activity (git log --oneline -30 with dates), and whether tests exist for each area (apps/web/__tests__, apps/web/lib/__tests__, e2e specs — read spec names, DO NOT RUN them).

Return findings as your final text message, organized per claim. Precision over volume: do not claim absence without having read the wiring. Quote decisive code snippets only where load-bearing.
