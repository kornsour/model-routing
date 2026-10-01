---
title: Investigate .github-private branches
terse: Triage seven .github-private branches to DELETE, PR or NEEDS-DECISION, verifying squash merges and leftover work.
repo: github-private
parent: harvested
allowed: ["REPORT.md"]
category: investigation
tags: [harvested, read-only, git, investigation]
stratum: A
max_turns: 40
agent_bash: ["git:*", "grep:*", "rg:*", "find:*", "wc:*", "head:*", "tail:*", "diff:*"]
history_script: ha-branch-triage-02.sh
harvest_id: f3c6cad9d0714503
draw_position: 3
adaptations: "Org renamed; absolute path replaced by the working directory; offline note added (local origin, gh results given inline, report written to REPORT.md ending in a json block for grading). Fixture repo and a 106-commit history with seven branches written for the task."
authorship: "Brief: harvested text (parent model wrote it). Fixture, history script, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** The repo is the current working directory; its `origin` is a local copy of the GitHub remote, so `git fetch` works. There is no `gh` and no network. The `gh` calls in the method return:
>
> - `gh pr list --head <branch> --state all` — `agent/portfolio-static-export-tracker`: MERGED #88 "docs: portfolio static-export tracker"; `chore/issue-31-analyzer-blocker`: MERGED #103 "feat(analyzer): composite action resolution"; `chore/issue-84-66-82-verification`: none; `docs/aws-domain-inventory-2026-08-14`: none; `docs/tailscale-key-expiry-reauth`: MERGED #99 "docs: tailscale re-auth notes", MERGED #100 "docs: tailscale ACL note"; `rescue/aws-denials`: none; `work/runner-ops-51-53-70`: MERGED #110 "docs: runner ops for #51 #53", CLOSED #111 "tools: drain a runner before maintenance".
> - `gh issue view <n>` — #31 OPEN "Workflow analyzer blocks on composite actions"; #47 OPEN "Tailscale node keys expire silently"; #51, #53, #66, #82, #84 CLOSED; #70 OPEN "Drain a runner before host maintenance".
> - `gh issue list --state open` — #31, #47, #70, #112 "Refresh the domain inventory quarterly", #115 "Record every AWS access denial with its fix".
>
> Write your report to `REPORT.md` at the repo root (that file is what gets read) and end it with a fenced `json` block of exactly this shape: `{"branches": {"<branch>": {"verdict": "DELETE" | "PR" | "NEEDS-DECISION", "open_issue": <number or null>}}}`, one entry per branch.

You are investigating git branches to decide, for each: DELETE (work already merged or obsolete) or PR (real unmerged work worth landing). You are READ-ONLY: do NOT push, do NOT delete anything, do NOT create PRs, do NOT commit. Investigate and report only.

## Repo

The current working directory (GitHub: Copperline/.github-private)

This repo is the org's config/docs/infrastructure source of truth. Its local clone is currently BEHIND origin - run `git fetch origin --prune` first and reason against `origin/main`.

## Branches to investigate

- `agent/portfolio-static-export-tracker` (18d, 1 commit ahead, no upstream)
- `chore/issue-31-analyzer-blocker` (3d, 7 commits ahead, behind 5)
- `chore/issue-84-66-82-verification` (3d, 1 commit ahead, ahead 1 behind 31)
- `docs/aws-domain-inventory-2026-08-14` (18d, 19 commits ahead, ahead 19 behind 106)
- `docs/tailscale-key-expiry-reauth` (5d, 3 commits ahead, behind 4)
- `rescue/aws-denials` (12d, 1 commit ahead, no upstream)
- `work/runner-ops-51-53-70` (3d, 2 commits ahead, no upstream)

KNOWN PRIOR FINDINGS (verify, don't just trust):
- `chore/issue-31-analyzer-blocker` has MERGED PR #103 but ALSO carries ~551 lines not in main - the PR merged an earlier state and the branch kept going.
- `docs/tailscale-key-expiry-reauth` has TWO merged PRs (#99, #100) and was then REUSED, picking up new commits including "chore: ignore .env and .DS_Store".
- `work/runner-ops-51-53-70` has MERGED#110 and a CLOSED#111.
These three are the pattern to watch: merged PR + extra unmerged work on top.

## Method (validated - follow it, don't invent your own)

Per branch:
1. `git fetch origin --prune --quiet` once up front.
2. Squash-merge check (this org squash-merges; ancestry alone finds almost nothing):
   ```
   mb=$(git merge-base main <branch>)
   d=$(git commit-tree $(git rev-parse <branch>^{tree}) -p $mb -m _)
   git cherry main $d       # "-" prefix = content already upstream
   ```
3. `git log --oneline main..<branch>` - what commits are actually unmerged.
4. For each commit subject, search main's history: `git log main --oneline --grep="<subject>"`. WATCH OUT for *integration* PRs that squash several branches under an unrelated title - inspect merge commit bodies (`git show --format=%b <sha>`) for the subject listed as a bullet.
5. Files on the branch absent from main: `git diff --name-only main...<branch>` + `git cat-file -e main:<file>`.
6. `gh pr list --repo Copperline/.github-private --head <branch> --state all --json number,state,title`
7. Open issues: branch names reference issue numbers (31, 84/66/82, 51/53/70, 47). For each referenced number: `gh issue view <n> --repo Copperline/.github-private --json number,title,state`. Also `gh issue list --repo Copperline/.github-private --state open --limit 60 --json number,title` to match work to open issues.

## Critical judgment rules

- A MERGED PR does NOT mean safe to delete - verify the branch has no *additional* unmerged content on top.
- Diff direction: `git diff main:<file> <branch>:<file>` showing DELETIONS means main has MORE content (main evolved past the branch) = branch is stale.
- `docs/aws-domain-inventory-2026-08-14` is 19 ahead but 106 behind - assess carefully whether its content is superseded by newer docs in main. NOTE: this repo has a strict convention that `docs/archive/` holds frozen historical records that must NEVER be updated or cited as current - if branch content targets archived docs, factor that in.
- Only recommend DELETE when you verified nothing unique would be lost.
- Recommend PR only if it could merge without reverting main; otherwise NEEDS-DECISION.

## Report format

Table, one row per branch:
`<branch> | VERDICT (DELETE/PR/NEEDS-DECISION) | unmerged commits | what's genuinely not in main (1 line) | PR state | related OPEN issue #`

Then a short prose section per NEEDS-DECISION / PR branch: what the unmerged work actually does, and which open issue it would close. For any branch you'd PR, state whether it merges cleanly against current main (check with `git merge-tree` or by assessing the behind-count and file overlap).

Be concise and factual. Say explicitly if you couldn't determine something.
