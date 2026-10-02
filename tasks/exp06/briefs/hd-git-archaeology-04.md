---
title: Git archaeology for the toolbelt changelog
terse: Answer the release-notes questions about toolbelt's history from git, read-only, in ANSWER.json.
repo: toolbelt
allowed: ["ANSWER.json"]
category: investigation
tags: [read-only, investigation, git]
stratum: D
max_turns: 40
agent_bash: ["git:*", "grep:*", "rg:*", "wc:*", "head:*", "tail:*"]
history_script: hd-git-archaeology-04.sh
harvest_shape: "read-only git investigation with a validated method and a fixed answer format (harvested #3/#13/#23: branch and history forensics)"
authorship: "Brief drafted from the shape of harvested read-only dispatches by Claude Opus 5.5; fixture history, answer key and reference answer by Claude Opus 5.5 (same family as the models under test)."
---
READ-ONLY. Do not modify, commit, tag or check out anything; leave the repository exactly as you found it, on `main`. Inspect older states with `git show <rev>:<path>`, `git log`, `git tag --contains` and the like. The only file you may create is `ANSWER.json` at the repo root.

We never kept a changelog for `toolbelt` (the current directory), and the first external users have asked for one. Before I write it I need some facts from the history, which is complete and tagged (`v0.1.0` … `v0.4.0`).

Answer in `ANSWER.json`, exactly this shape:

```json
{
  "truncate_fix_commit": "<commit subject>",
  "truncate_at_v0_1_0": "<what truncate('abcdefgh', 6) returned in v0.1.0>",
  "numbers_commit_count": 0,
  "pct_na_first_tag": "vX.Y.Z",
  "iterutil_first_tag": "vX.Y.Z",
  "slugify_last_author": "<author name>",
  "commits_v0_3_0_to_v0_4_0": 0
}
```

- `truncate_fix_commit`: the subject of the commit after which `truncate`'s result never exceeds `width` (the ellipsis counts inside the width).
- `truncate_at_v0_1_0`: the exact string the v0.1.0 code returned for that call.
- `numbers_commit_count`: how many commits changed `src/toolbelt/numbers.py`.
- `pct_na_first_tag`: the first tag in which `pct(1, 0)` returns `'n/a'` instead of raising.
- `iterutil_first_tag`: the first tag that ships `toolbelt.iterutil`.
- `slugify_last_author`: the author of the most recent commit that changed `slugify`'s behaviour.
- `commits_v0_3_0_to_v0_4_0`: commits reachable from `v0.4.0` but not from `v0.3.0`.
