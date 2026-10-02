# .github-private branch triage

| branch | VERDICT | unmerged commits | what's genuinely not in main | PR state | related OPEN issue |
|---|---|---|---|---|---|
| agent/portfolio-static-export-tracker | DELETE | 1 | nothing: `git cherry` gives `-`, squash-merged as #88 | MERGED #88 | - |
| chore/issue-31-analyzer-blocker | PR | 7 (3 landed via #103) | `tools/workflow-analyzer/checks-1..4.sh`, ~556 lines | MERGED #103 | #31 |
| chore/issue-84-66-82-verification | DELETE | 1 | nothing: the line landed inside integration squash #95 (bullet in its body) | none | - |
| docs/aws-domain-inventory-2026-08-14 | DELETE | 19 | nothing: every row is in `docs/DOMAINS.md`; the file it edits is now archived | none | #112 |
| docs/tailscale-key-expiry-reauth | PR | 3 | `docs/TAILSCALE-REAUTH.md` (the .gitignore commit is already on main via #107) | MERGED #99, #100 | #47 |
| rescue/aws-denials | DELETE | 1 | nothing: its three rows are in `docs/AWS-ACCESS-DENIALS.md` | none | #115 |
| work/runner-ops-51-53-70 | NEEDS-DECISION | 2 (1 landed via #110) | the `drain` command in `tools/runner-ops.sh` | MERGED #110, CLOSED #111 | #70 |

**chore/issue-31-analyzer-blocker (PR).** Four commits after the #103 squash add the composite-action check batches; nothing on main touches `tools/workflow-analyzer/` since, and `git merge-tree` is clean. Closes #31.

**docs/tailscale-key-expiry-reauth (PR).** Two docs commits add the expired-key re-auth runbook and the tagged-node policy; merges cleanly (the `.gitignore` change is identical on both sides). Closes #47.

**work/runner-ops-51-53-70 (NEEDS-DECISION).** The drain command (#70) was in closed PR #111 and conflicts with main's #114 rewrite of `tools/runner-ops.sh` (now driven by `runners.json`). Port the drain command onto the new script rather than merging.

```json
{
 "branches": {
  "agent/portfolio-static-export-tracker": {
   "verdict": "DELETE",
   "open_issue": null
  },
  "chore/issue-31-analyzer-blocker": {
   "verdict": "PR",
   "open_issue": 31
  },
  "chore/issue-84-66-82-verification": {
   "verdict": "DELETE",
   "open_issue": null
  },
  "docs/aws-domain-inventory-2026-08-14": {
   "verdict": "DELETE",
   "open_issue": 112
  },
  "docs/tailscale-key-expiry-reauth": {
   "verdict": "PR",
   "open_issue": 47
  },
  "rescue/aws-denials": {
   "verdict": "DELETE",
   "open_issue": 115
  },
  "work/runner-ops-51-53-70": {
   "verdict": "NEEDS-DECISION",
   "open_issue": 70
  }
 }
}
```
