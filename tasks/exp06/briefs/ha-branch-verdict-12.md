---
title: Investigate folio-site feat/aws-static-site
terse: Decide whether folio-site's feat/aws-static-site branch should be deleted, PR'd, or needs a decision, with the git evidence.
repo: folio-site
parent: harvested
allowed: ["REPORT.md"]
category: investigation
tags: [harvested, read-only, git, investigation]
stratum: A
max_turns: 40
agent_bash: ["git:*", "grep:*", "rg:*", "find:*", "wc:*", "head:*", "tail:*"]
history_script: ha-branch-verdict-12.sh
harvest_id: 7792fc6a72a2ec8d
draw_position: 38
adaptations: "Personal account, org and repos renamed; absolute path replaced by the working directory; offline note added (local origin, gh results given inline, report written to REPORT.md ending in a json block for grading). Fixture repo and git history written for the task."
authorship: "Brief: harvested text (parent model wrote it). Fixture, history script, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** The repo is the current working directory: a clone of ellisport/folio-site whose `origin` is a local copy of the GitHub remote, so `git fetch` works. There is no `gh` and no network; the two `gh` calls in the method return:
>
> - `gh pr list --repo ellisport/folio-site --head feat/aws-static-site --state all --json number,state,title` → `[]`
> - `gh issue list --repo ellisport/folio-site --state open --search "AWS static site deploy migration"` → `#7 Add a contact page`
>
> Write your report to `REPORT.md` at the repo root (that file is what gets read) and end it with a fenced `json` block of exactly this shape: `{"verdict": "DELETE" | "PR" | "NEEDS-DECISION", "absent_from_main": {"infra": [paths], "application": [paths]}, "behind": <int>}`.

You are investigating one git branch to determine if it should be DELETED (work already merged/obsolete) or turned into a PR (real unmerged work worth landing), or is a NEEDS-DECISION case. You are READ-ONLY: do not push, delete, commit, or create PRs.

Repo: the current working directory
Branch: feat/aws-static-site (owner for gh commands: ellisport, repo name: folio-site)
Known starting point: ~19 days old, 1 commit ahead of main, 27 commits BEHIND main. This clone is known to be behind upstream — you MUST fetch first. Note the branch name is different from the others (feat/aws-static-site, not feat/aws-staging) — this repo may be a static site (not SST-based like the others), so verify actual content rather than assuming.

CONTEXT — a sibling repo "mise" (different org, Copperline) was already investigated as a model case: its feat/aws-staging branch adds SST-based infra (sst.config.ts, sst-env.d.ts, .github/workflows/aws-staging.yml) plus genuinely unmerged application code (specific .ts files absent from main). But main had since moved to a script-based deploy (apps/web/scripts/deploy-aws.sh), making the SST approach look SUPERSEDED, and the branch was very far behind (huge deletion count if merged), so verdict was NEEDS-DECISION (preserve, don't delete, don't blindly PR). Your job: run the same rigorous investigation on folio-site and report the real facts for THIS repo — don't assume the same verdict applies without verifying, and don't assume the same tech stack (SST/apps-web layout) — this is under a different GitHub owner (ellisport, personal account) and may be structured completely differently (e.g. a plain static site deployed to S3/CloudFront rather than SST).

METHOD (run these commands, adapt paths accordingly):
1. `git fetch origin --prune --quiet`
2. Default branch is main.
3. Squash-merge check (org squash-merges, so plain ancestry checks find almost nothing):
   ```
   mb=$(git merge-base main feat/aws-static-site)
   d=$(git commit-tree $(git rev-parse feat/aws-static-site^{tree}) -p $mb -m _)
   git cherry main $d
   ```
   A "-" prefix on the result means that content is already upstream (merged). No "-" prefix (a "+") means it's not found upstream.
4. KEY TEST — files on the branch not in main at all:
   `git diff --name-only main...feat/aws-static-site` then for each file check `git cat-file -e main:<file>` (nonzero exit = absent from main). List files ABSENT from main, separating infra scaffolding (IaC/config/workflow files) from real application/content code (actual site/logic files). Application code absent from main = work that would be LOST if branch is deleted.
5. Check if deploy approach is superseded: `git ls-tree -r --name-only main | grep -iE "sst\.config|deploy-aws|aws|deploy|cloudfront|s3"` — see what main currently uses for deployment, if anything.
6. `git rev-list --count feat/aws-static-site..main` (how far behind) and `git diff --shortstat main..feat/aws-static-site` (large deletion counts = merging would revert main's progress).
7. `gh pr list --repo ellisport/folio-site --head feat/aws-static-site --state all --json number,state,title`
8. `gh issue list --repo ellisport/folio-site --state open --search "AWS static site deploy migration"` — list any candidate related issues with number/title.

Also note: per this org's CLAUDE.md context, folio-site's AWS deployment work targets a "Secondary" AWS account that was demoted (workload_deployments_allowed: false) and is described as "plan-only state" — check if the branch content is consistent with that (i.e. never actually deployed) as additional context for your verdict, but base your verdict primarily on the git evidence.

JUDGMENT RULES:
- Diff direction matters: `git diff main:<file> feat/aws-static-site:<file>` showing content REMOVED relative to branch (i.e. main has MORE / different) means main evolved past the branch — evidence branch is stale on that file.
- A branch far behind main WITH unmerged app code is NOT simply deletable and NOT simply PR-able — that's NEEDS-DECISION. Say exactly which files would be lost and whether the approach looks superseded.
- Only recommend DELETE when you've verified nothing unique (no app/content code) would be lost — infra scaffolding alone (regenerable) leaning toward DELETE is fine if that's genuinely all there is AND it's superseded.
- Only recommend PR when the branch could actually merge without reverting main (i.e., not massively behind with huge deletion counts).

Report back concisely with:
- VERDICT: DELETE, PR, or NEEDS-DECISION
- List of files absent from main, split into infra vs application/content code (name the application code files explicitly)
- behind-by count, shortstat summary
- whether main's deploy approach supersedes the branch's approach (what main uses now, if anything)
- any open issue numbers/titles found
- existing PR (if any) for this branch, state
- one paragraph justifying the verdict

Keep your final report under 400 words plus the file lists.
