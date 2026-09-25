# 2026-09-25 · exp05 confirmatory run, stage 1

Pre-registered run (`exp05_dispatch/20260924-125257`, registered at
`aa0d54c`, Claude track, `claude` 2.1.278): 65 tasks × 3 trials × `B`,
`C1_inline`, `static_haiku`, `static_sonnet`, randomized blocks. 780 graded
cells, **$202.33** list price, 16 h of clock time (stopped once at 336 cells
and resumed to raise the budget from $150 to $230). The report marks it
**confirmatory**. No usage limits, no provider outages; $0.08 was spent on the
one cell interrupted by the stop.

| policy | pass rate | cost / completed task (95% CI) | mean turns |
|---|---:|---:|---:|
| `B` (spawn on Opus) | 99% | $0.528 ($0.454-$0.599) | 14.6 |
| `C1_inline` (parent picks) | 100% | $0.129 ($0.104-$0.167) | 9.3 |
| `static_haiku` | 84% | $0.239 ($0.200-$0.293) | 26.3 |
| `static_sonnet` | 100% | $0.099 ($0.090-$0.109) | 7.4 |
| oracle (hindsight) | 100% | $0.098 | - |

**H-D1 supported:** `C1_inline` vs `B` saves 76% (CI 70-80%) at +0.5 pts pass
rate (CI +0 to +1.5); 50% (CI 43-55%) when the whole router turn is billed.
Subgroup on measured-medium tasks: 80% saving, 100% pass.

**Exploratory, not pre-registered, and the practical headline:** always
Sonnet beats the router by 23% per completed task (router +30%, CI +9% to
+59%). The router picked Sonnet 87% of the time; its 7 Opus picks ($0.85 per
task) and 19 Haiku picks (slightly dearer than Sonnet on the same cells)
only added cost. Always Haiku costs 2.4× always Sonnet per completed task
(CI 2.1-2.8×) because it fails 16% of cells and takes 3.5× the turns. On
this task set the saving comes from not defaulting to the frontier model, not
from per-task routing. Cheapest per token is not cheapest per task.

Paper draft: `docs/paper/exp05-dispatch-routing.md` (prose filled in; figure
`docs/paper/exp05-pareto.svg`). Raw data backed up to the Google Drive folder.
