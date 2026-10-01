---
title: Investigate trackbook, crossfade and stale refs
terse: Triage five branches across four repos and explain two stale remote-tracking refs, without changing anything.
repo: branch-fleet
parent: harvested
allowed: ["REPORT.md"]
category: investigation
tags: [harvested, read-only, git, investigation, multi-repo]
stratum: A
max_turns: 40
visible_cmd: ["git", "status", "--short"]
agent_bash: ["git:*", "grep:*", "rg:*", "find:*", "wc:*", "head:*", "tail:*", "diff:*"]
history_script: ha-branch-triage-08.sh
harvest_id: 5d09c174c9413fc4
draw_position: 13
adaptations: "Org, personal account and repos renamed; absolute paths replaced by paths under the working directory; offline note added (local origins, gh results given inline, report written to REPORT.md ending in a json block for grading). Six fixture clones and their histories written for the task."
authorship: "Brief: harvested text (parent model wrote it). Fixture, history script, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** Each repository is a clone under the current working directory at the path given below; each has an `origin` that is a local copy of its GitHub remote, so `git fetch` and `git ls-remote` work. There is no `gh` and no network. The `gh` calls in the method return: `gh pr list --head <branch>` is empty for every branch listed; open issues are trackbook #12 "Python client contract tests" and #20 "Publish the client to PyPI", crossfade #29 "M6: evaluation harness for beat matching" and #33 "Windows build", packlight #64 "Trip sharing permissions", and none for ml-notes.
>
> Write your report to `REPORT.md` at the top of the working directory (that file is what gets read) and end it with a fenced `json` block of exactly this shape: `{"branches": {"<repo>:<branch>": {"verdict": "DELETE" | "PR" | "LEAVE-ALONE" | "NEEDS-DECISION", "open_issue": <number or null>}}, "stale_refs": {"mise": {"cause": "...", "safe_to_prune": true | false, "cleanup": "<exact command>", "config_change_needed": true | false}, "binwise": {...}}}`.

You are investigating git branches to decide, for each: DELETE (work already merged or obsolete) or PR (real unmerged work worth landing). You are READ-ONLY: do NOT push, do NOT delete anything, do NOT create PRs, do NOT commit. Investigate and report only.

## Part 1 - branches

trackbook (ellisport/trackbook, owner ellisport):
- `examples-and-diff-verdict-fix` (4d, 3 commits ahead, no upstream)
- `python-client-contract` (4d, 6 commits ahead, no upstream)

crossfade (Copperline/crossfade, owner Copperline):
- `feat/m6-eval` (34d, 7 commits ahead, no upstream)

packlight (Copperline/packlight, owner Copperline):
- `fix/nanoid-3-3-18` (12d, 1 commit ahead, no upstream) - a dependency/security bump

ml-notes (Copperline/ml-notes, owner Copperline):
- `learn` (STALE: last commit 2026-07-19, 6 commits unmerged) - the only branch old enough to be flagged stale (>45 days)

## Part 2 - two stale local remote-tracking refs

These are NOT branches. They are refs under `refs/remotes/origin/` that have no matching branch on the real remote - almost certainly artifacts of a locally configured mirror/fork fetch refspec:
- mise: `origin/upstream/main`  (Copperline/mise)
- binwise: `origin/canonical/main`  (Copperline/binwise)

For each, determine WHY it exists and whether it's safe to prune locally:
- `git config --get-regexp 'remote\..*\.fetch'` and `git remote -v` in that repo - is there a custom refspec or an extra remote creating it?
- `git ls-remote --heads origin | grep -E 'upstream|canonical'` - confirm no such branch exists on the real remote.
- `git log -1 --format='%h %s %cr' refs/remotes/origin/upstream/main` (resp. canonical/main) - what does it point at, and is that commit already in main?
- Report the exact command that would clean it up (e.g. `git update-ref -d`) and whether any git config would need changing to stop it coming back. Do NOT run any cleanup.

## Method for Part 1 (validated - follow it, don't invent your own)

1. `git fetch origin --prune --quiet` first. Local clones go stale.
2. Default branch is `main`.
3. Squash-merge check (these orgs squash-merge, so ancestry alone finds almost nothing):
   ```
   mb=$(git merge-base main <branch>)
   d=$(git commit-tree $(git rev-parse <branch>^{tree}) -p $mb -m _)
   git cherry main $d      # "-" prefix = content already upstream
   ```
4. `git log --oneline main..<branch>` - the actually-unmerged commits.
5. Search main history for each commit subject: `git log main --oneline --grep="<subject>"`. WATCH OUT for *integration* PRs squashing several branches under an unrelated title - check merge bodies with `git show --format=%b <sha>`.
6. Files absent from main: `git diff --name-only main...<branch>` + `git cat-file -e main:<file>`.
7. `gh pr list --repo <owner>/<repo> --head <branch> --state all --json number,state,title`
8. Open issues: `gh issue list --repo <owner>/<repo> --state open --limit 50 --json number,title` - match each branch's work to an open issue by topic (eval harness/M6, python client contract, examples & diff verdicts, nanoid CVE).
9. For `packlight:fix/nanoid-3-3-18` specifically: check whether nanoid is ALREADY bumped in main (`git show main:package.json | grep -i nanoid`, and check the lockfile). Security bumps are frequently superseded by a later dependabot PR - if main already has >= 3.3.18, the branch is obsolete.
10. For `ml-notes:learn`: it's 45+ days stale. Determine whether it's an abandoned experiment or unfinished real work. Look at what the 6 commits actually contain.

## Critical judgment rules

- A MERGED PR does NOT mean safe to delete - verify no *additional* unmerged commits sit on top.
- Diff direction: `git diff main:<file> <branch>:<file>` showing DELETIONS means main has MORE content (main evolved past the branch) = branch stale.
- Only recommend DELETE when you verified nothing unique would be lost.
- Recommend PR only if it could merge without reverting main; otherwise NEEDS-DECISION.

## Report format

Part 1 table, one row per branch:
`<repo>:<branch> | VERDICT (DELETE/PR/LEAVE-ALONE/NEEDS-DECISION) | unmerged commits | what the work does (1 line) | PR state | related OPEN issue #`

For each PR verdict: proposed PR title, the issue it closes, and whether it merges cleanly against current main.

Part 2: for each of the two stale refs - why it exists, whether it's safe to prune, the exact cleanup command, and any config change needed to stop it recurring.

Be concise and factual. Say explicitly if you couldn't determine something.
