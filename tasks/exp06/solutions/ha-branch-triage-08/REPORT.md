# Branch and stale-ref triage

## Part 1

| repo:branch | VERDICT | unmerged commits | what the work does | PR state | related OPEN issue |
|---|---|---|---|---|---|
| trackbook:examples-and-diff-verdict-fix | DELETE | 3 | examples + diff verdict fix, all inside integration squash #18 (bullets in its body) | none | - |
| trackbook:python-client-contract | PR | 6 | Python client contract tests | none | #12 |
| crossfade:feat/m6-eval | NEEDS-DECISION | 7 | M6 eval cases in `eval/run.py`; main moved to a table-driven `evals/` harness, so it conflicts | none | #29 |
| packlight:fix/nanoid-3-3-18 | DELETE | 1 | nanoid 3.3.18; main already has 3.3.19 (#58) | none | - |
| ml-notes:learn | LEAVE-ALONE | 6 | abandoned scratch notes (`scratch/attention.md`, "wip" commits, July) | none | - |

**trackbook:python-client-contract** -> PR "test(python): client contract tests", closes #12; only adds `python/tests/`, merges cleanly.

## Part 2

- **mise `origin/upstream/main`**: remote `upstream` (the template) has `fetch = +refs/heads/*:refs/remotes/origin/upstream/*`, so every `git fetch upstream` writes under `origin/`. No such branch on origin. The commit is the template's main, an ancestor of mise main. Safe to prune: `git update-ref -d refs/remotes/origin/upstream/main`, and fix the refspec (`git config --replace-all remote.upstream.fetch '+refs/heads/*:refs/remotes/upstream/*'`) or it comes back.
- **binwise `origin/canonical/main`**: no remote or refspec creates it (leftover of a removed remote); it points at a commit already in main. Safe to prune: `git update-ref -d refs/remotes/origin/canonical/main`. No config change needed.

```json
{
 "branches": {
  "trackbook:examples-and-diff-verdict-fix": {
   "verdict": "DELETE",
   "open_issue": null
  },
  "trackbook:python-client-contract": {
   "verdict": "PR",
   "open_issue": 12
  },
  "crossfade:feat/m6-eval": {
   "verdict": "NEEDS-DECISION",
   "open_issue": 29
  },
  "packlight:fix/nanoid-3-3-18": {
   "verdict": "DELETE",
   "open_issue": null
  },
  "ml-notes:learn": {
   "verdict": "LEAVE-ALONE",
   "open_issue": null
  }
 },
 "stale_refs": {
  "mise": {
   "cause": "remote 'upstream' has fetch refspec +refs/heads/*:refs/remotes/origin/upstream/*",
   "safe_to_prune": true,
   "cleanup": "git update-ref -d refs/remotes/origin/upstream/main",
   "config_change_needed": true
  },
  "binwise": {
   "cause": "leftover ref from a removed remote; no refspec creates it",
   "safe_to_prune": true,
   "cleanup": "git update-ref -d refs/remotes/origin/canonical/main",
   "config_change_needed": false
  }
 }
}
```
