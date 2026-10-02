---
title: Archive convention: ellisport/ts-starter
terse: Set up an archive folder in the ts-starter template repo and point its root docs at it; move only clearly historical docs.
repo: ts-starter
parent: harvested
allowed: ["archive/*", "docs/*", "README.md", "CLAUDE.md", "AGENTS.md", "PR_BODY.md", "CHANGELOG.md"]
category: docs
tags: [harvested, docs, judgment, batch-identical]
stratum: A
max_turns: 40
visible_cmd: ["node", "--test"]
agent_bash: ["git:*", "mkdir:*", "mv:*", "node:*", "npm test"]
harvest_id: e576cc94c65bda59
draw_position: 11
adaptations: "Personal account and repo renamed; absolute path replaced by the working directory; offline note added (no remote: the 1-commit-behind clause no longer applies, skip the fetch/fast-forward in step 2 and the push/PR in steps 8-9, write the PR body to PR_BODY.md). Fixture repo written for the task."
authorship: "Brief: harvested text (parent model wrote it). Fixture, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** The repo is the current working directory; it is already a git checkout on its default branch `main`, and in this copy it is level with upstream. There is no remote and no `gh`: skip the fetch and fast-forward in step 2 (the branch is current) and skip steps 8 and 9 (push and PR). Instead, write the PR body you would have opened to `PR_BODY.md` at the repo root.

Repo: the current working directory (GitHub slug ellisport/ts-starter)

You are setting up an "archive" documentation convention in this repo and opening a PR, as part of a batch of identical tasks across ~38 of the user's repos. Work ONLY inside this repo directory. Note: this local clone is known to be 1 commit behind origin/main as of session start — make sure step 2 actually brings it level. This is a public GitHub "template" repo — the archive convention is still worth applying so anyone using it as a template inherits the pattern.

1. `cd` into the repo path above. Run `git status --short`. If there are uncommitted local changes (staged or unstaged) or untracked files that look like in-progress work, STOP and report "skipped: dirty working tree" — do not touch anything else in this repo.

2. Determine the default branch: try `git symbolic-ref refs/remotes/origin/HEAD` (strip `refs/remotes/origin/`), falling back to `gh repo view ellisport/ts-starter --json defaultBranchRef -q .defaultBranchRef.name` if needed. Checkout that branch locally, `git fetch origin`, then `git merge --ff-only origin/<default>` to bring the local clone level with upstream. If the fast-forward fails, STOP and report "skipped: local branch diverged from origin, needs manual resolution".

3. Create a new branch off the now-current default branch: `git switch -c docs/archive-convention`.

4. Decide where the archive folder goes: if a top-level `docs/` directory already exists in this repo and holds multiple markdown docs, use `docs/archive/`; otherwise use a top-level `archive/`. Create that directory with its own `README.md` explaining its purpose in your own words, covering: this folder holds historical/superseded documentation and records; content here reflects past decisions, plans, or state and must NOT be used to understand the current state of the project or to guide new work; contributors and coding agents should treat everything under this folder as historical context only, never as current truth.

5. Investigate this repo's existing documentation for anything that is CLEARLY superseded/historical — read the top-level README.md, CLAUDE.md, AGENTS.md (whichever exist), and any files under `docs/` or similar. This is a template/starter repo so it likely has nothing historical. Be CONSERVATIVE — only move a file when you are confident it is unambiguously historical; when in doubt, leave it alone. Move whole files only using `git mv <file> <archive-dir>/`. If nothing qualifies, don't force it, just note that in your report.

6. For each of `CLAUDE.md`, `AGENTS.md`, `README.md` that ALREADY EXISTS at the repo root (do NOT create any of these files if they don't exist), add a short note (2-4 sentences) pointing at the archive folder you created/used, stating clearly that its contents are historical records only and must not be treated as current or used to inform new work. Place the note somewhere sensible. Keep the edit minimal and surgical.

7. Review your changes: `git status`, `git diff --stat`. Stage everything relevant with `git add`. Commit with a clear message, e.g.:
   "Establish archive/ convention for historical docs"
   with a body noting what was created and what (if anything) was moved. End the commit message with:
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

8. Push the branch: `git push -u origin docs/archive-convention`.

9. Open a PR with `gh pr create --title "Establish archive convention for historical docs" --body "..."`. The body must clearly list: (a) where the archive folder was created and why that location, (b) which of CLAUDE.md/AGENTS.md/README.md were updated, (c) an itemized list of any files moved into the archive folder, each with a one-line justification, (d) explicitly note if nothing was moved.

10. Report back concisely: repo slug, PR URL (or the reason you skipped/stopped), archive folder path chosen, list of doc files edited, list of files moved with justification (or "none moved").

Notes: this is a personal (ellisport) repo, not org-governed, but still create a PR rather than pushing directly to the default branch. `gh` is already authenticated in this environment. Do not merge the PR — just open it.
