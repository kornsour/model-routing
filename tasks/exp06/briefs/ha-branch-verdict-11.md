---
title: Investigate packlight feat/aws-staging
terse: Decide whether packlight's feat/aws-staging branch should be deleted, PR'd, or needs a decision, with the git evidence.
repo: packlight-app
parent: harvested
allowed: ["REPORT.md"]
category: investigation
tags: [harvested, read-only, git, investigation]
stratum: A
max_turns: 40
visible_cmd: ["node", "--test"]
agent_bash: ["git:*", "grep:*", "rg:*", "find:*", "wc:*", "head:*", "tail:*"]
history_script: ha-branch-verdict-11.sh
harvest_id: db30375730ca1b5d
draw_position: 23
adaptations: "Org and repos renamed; absolute path replaced by the working directory; offline note added (local origin, gh results given inline, report written to REPORT.md ending in a json block for grading). Fixture repo and git history written for the task."
authorship: "Brief: harvested text (parent model wrote it). Fixture, history script, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** The repo is the current working directory: a clone of Copperline/packlight whose `origin` is a local copy of the GitHub remote, so `git fetch` works. There is no `gh` and no network; the two `gh` calls in the method return:
>
> - `gh pr list --repo Copperline/packlight --head feat/aws-staging --state all --json number,state,title` → `[]`
> - `gh issue list --repo Copperline/packlight --state open --search "AWS staging deploy migration"` → `#41 Staging environment on AWS`
>
> Write your report to `REPORT.md` at the repo root (that file is what gets read) and end it with a fenced `json` block of exactly this shape: `{"verdict": "DELETE" | "PR" | "NEEDS-DECISION", "absent_from_main": {"infra": [paths], "application": [paths]}, "behind": <int>}`.

You are investigating one git branch to determine if it should be DELETED (work already merged/obsolete) or turned into a PR (real unmerged work worth landing), or is a NEEDS-DECISION case. You are READ-ONLY: do not push, delete, commit, or create PRs.

Repo: the current working directory
Branch: feat/aws-staging (owner for gh commands: Copperline, repo name: packlight)
Known starting point: ~19 days old, 1 commit ahead of main, 11 commits BEHIND main.

CONTEXT — a sibling repo "mise" was already investigated as a model case: its feat/aws-staging branch adds SST-based infra (sst.config.ts, sst-env.d.ts, .github/workflows/aws-staging.yml) plus genuinely unmerged application code (specific .ts files absent from main). But main had since moved to a script-based deploy (apps/web/scripts/deploy-aws.sh), making the SST approach look SUPERSEDED, and the branch was very far behind (huge deletion count if merged), so verdict was NEEDS-DECISION (preserve, don't delete, don't blindly PR). Your job: run the same rigorous investigation on packlight and report the real facts for THIS repo — don't assume the same verdict applies without verifying.

METHOD (run these commands, adapt paths accordingly):
1. `git fetch origin --prune --quiet`
2. Default branch is main.
3. Squash-merge check (org squash-merges, so plain ancestry checks find almost nothing):
   ```
   mb=$(git merge-base main feat/aws-staging)
   d=$(git commit-tree $(git rev-parse feat/aws-staging^{tree}) -p $mb -m _)
   git cherry main $d
   ```
   A "-" prefix on the result means that content is already upstream (merged). No "-" prefix (a "+") means it's not found upstream.
4. KEY TEST — files on the branch not in main at all:
   `git diff --name-only main...feat/aws-staging` then for each file check `git cat-file -e main:<file>` (nonzero exit = absent from main). List files ABSENT from main, separating infra scaffolding (sst.config.ts, sst-env.d.ts, workflow yml files) from real application/source code (e.g. .ts/.tsx/.py files with actual logic). Application code absent from main = work that would be LOST if branch is deleted.
5. Check if deploy approach is superseded: `git ls-tree -r --name-only main | grep -iE "sst\.config|deploy-aws|aws|deploy"` — see what main currently uses for deployment.
6. `git rev-list --count feat/aws-staging..main` (how far behind) and `git diff --shortstat main..feat/aws-staging` (large deletion counts = merging would revert main's progress).
7. `gh pr list --repo Copperline/packlight --head feat/aws-staging --state all --json number,state,title`
8. `gh issue list --repo Copperline/packlight --state open --search "AWS staging deploy migration"` — list any candidate related issues with number/title.

JUDGMENT RULES:
- Diff direction matters: `git diff main:<file> feat/aws-staging:<file>` showing content REMOVED relative to branch (i.e. main has MORE / different) means main evolved past the branch — evidence branch is stale on that file.
- A branch far behind main WITH unmerged app code is NOT simply deletable and NOT simply PR-able — that's NEEDS-DECISION. Say exactly which files would be lost and whether the approach looks superseded.
- Only recommend DELETE when you've verified nothing unique (no app code) would be lost — infra scaffolding alone (sst.config.ts etc, easily regenerable) leaning toward DELETE is fine if that's genuinely all there is AND it's superseded.
- Only recommend PR when the branch could actually merge without reverting main (i.e., not massively behind with huge deletion counts).

Report back concisely with:
- VERDICT: DELETE, PR, or NEEDS-DECISION
- List of files absent from main, split into infra vs application code (name the application code files explicitly)
- behind-by count, shortstat summary
- whether main's deploy approach supersedes the branch's approach (what main uses now)
- any open issue numbers/titles found
- existing PR (if any) for this branch, state
- one paragraph justifying the verdict

Keep your final report under 400 words plus the file lists.
