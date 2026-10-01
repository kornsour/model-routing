---
title: Sweep rulesets and branch protection
terse: Inventory org rulesets, repo rulesets and legacy branch protection across both owners and answer the four enforcement questions.
repo: ruleset-sweep
parent: harvested
allowed: ["REPORT.md"]
category: investigation
tags: [harvested, read-only, ci, governance, inventory]
stratum: A
max_turns: 40
visible_cmd: ["python3", "-c", "import json, pathlib; [json.loads(p.read_text()) for p in pathlib.Path('gh-snapshot').rglob('*.json')]"]
agent_bash: ["jq:*", "grep:*", "rg:*", "find:*", "wc:*", "head:*", "ls:*"]
harvest_id: ab845499cec98356
draw_position: 17
adaptations: "Org and personal account renamed; scratchpad deliverable path replaced by REPORT.md; offline note added (gh api responses saved under gh-snapshot/, answers ending REPORT.md as a json block for grading). Snapshot of 48 repos, their rulesets, protection and workflows generated for the task; answer key derived from it by a reference solver."
authorship: "Brief: harvested text (parent model wrote it). Snapshot generator, reference solver, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** There is no network and no `gh`. Every `gh api` response the sweep needs was captured at one moment and saved under `gh-snapshot/` by API path; `gh-snapshot/README.md` maps each endpoint to its file. Treat the snapshot as the live API. End `REPORT.md` with a fenced `json` block of exactly this shape (that block is what gets read): `{"no_enforcement": ["owner/repo", ...], "mismatched_contexts": {"owner/repo": ["context", ...]}, "strict": ["owner/repo", ...], "missing_properties": {"owner/repo": ["property", ...]}, "archived_skipped": <int>, "scanned": <int>}`, where `mismatched_contexts` lists every required context string on a repo's default branch that no job in that repo produces, and `missing_properties` lists, per org repo, each custom property used by an org ruleset's targeting that the repo has unset.

READ-ONLY INVENTORY. Make no changes — do not create, edit, or delete any ruleset or branch protection. Report only.

Goal: map where merge enforcement lives — ORG-level rulesets vs REPO-level rulesets vs legacy branch protection — for owner `Copperline` (~22 repos, include the repo literally named `.github-private`) and owner `ellisport` (~23 public repos). Live `gh api` is the source of truth. Skip archived repos but report how many.

Collect:
1. ORG rulesets: `gh api /orgs/Copperline/rulesets` and then each one's detail (`/orgs/Copperline/rulesets/{id}`). For each: name, enforcement, target, what it REQUIRES (required status checks and their exact context strings, PR review requirements, required-branches-up-to-date / `strict_required_status_checks_policy`, linear history, signatures, etc), and its CONDITIONS — especially whether it targets repos by org custom property (`stack`, `database`, `deploys`, `tier`, `ci-managed`, `orm`) or by name.
2. REPO-level rulesets: `gh api /repos/{owner}/{repo}/rulesets` for every repo. Same detail. These duplicate/conflict with org rulesets and are worth flagging.
3. LEGACY branch protection: `gh api /repos/{owner}/{repo}/branches/{default}/protection` (404 = none). Report which repos still have it.
4. For each repo, resolve the EFFECTIVE required checks — the union actually enforced on its default branch — and note where they come from (org ruleset / repo ruleset / legacy).

Then answer these specific questions:
- Which repos have NO enforcement at all on their default branch?
- Where do required status check CONTEXT STRINGS not match any job name that repo actually produces? A required check that never runs blocks merges forever; a check named slightly differently is silently not enforced. Cross-check the context strings against the job names in that repo's `.github/workflows/`.
- Which repos carry `strict_required_status_checks_policy` (require branch up to date)? This one is expensive: it forces re-runs of the full suite every time main moves, and this org is over its Actions minutes allowance, so list these explicitly.
- Which repos are missing any of the org custom properties used for ruleset targeting? A repo missing a property silently falls outside its ruleset with no error.

CRITICAL TRAPS:
1. Default shell is zsh; bash `[[ =~ ]]`/`BASH_REMATCH` silently matches nothing. Use `bash -c` for bash logic.
2. `for r in Owner/*/` skips dot-directories — `.github-private` would be silently omitted. Use the API.
3. Piping into `head`/`tail` masks exit codes.
4. `timeout` does not exist on macOS.
5. A 404 from the protection endpoint means "no legacy protection", not an error — distinguish that from a permissions failure (403), and say so if you hit permission limits rather than reporting "none".

Deliverable: write a markdown report to
REPORT.md (at the top of the working directory)
with: (1) org rulesets table, (2) repo-level rulesets table, (3) legacy branch protection list, (4) per-repo effective-enforcement table, (5) answers to the four questions above, (6) how many repos you actually scanned. Then return a concise summary of the most important findings.
