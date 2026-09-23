# 2026-09-23 · exp05 smoke of the untested policy paths

Real run on the Claude track (subscription login, `claude` 2.1.278, harness
at `6e8e438`): `exp05_smoke_paths`, 2 hard `-01` tasks × 5 policies × 1
trial, $3.21 list price. Not a hypothesis test; it checks that the paths the
2026-09-22 pilot never exercised on real models behave as designed before
the confirmatory run.

| path | what was checked | result |
|---|---|---|
| `A` (resume the seeded parent, no fork) | worker session id equals the setup session id; worker edited files | as designed, 2/2 passed |
| `A_switch` (resume, switch Opus → Sonnet mid-session) | resolved model of the worker is `claude-sonnet-5` on the parent's session id | as designed, 2/2 passed |
| `C1_inline` (brief + pick in one forked turn) | router got a new session id (fork), `cost_usd_billed` is the marginal pick ($0.0006-$0.002) while the full turn cost $0.09-$0.13; worker ran on the canned brief | as designed, 2/2 passed |
| `D` escalation | cascade escalates when the cheapest model fails the visible checks | **not exercised**: Haiku passed both `-01` hard tasks on the first attempt. Re-smoke on a task the calibration run shows Haiku failing |

One defect found and fixed (`7c9f…`, this branch): on `inv-retry-01` the
parent answered the tools-off inline turn with "I'll take a quick look at
`sync.py`", tried to read a file, and the turn ended without a pick. The
policy fell back to the parent model silently. The prompt now says tools are
disabled for the reply, and every `C1*` outcome records `router_fallback`;
the report shows the fallback rate per policy. A fallback biases routing
toward `B` (never away from it), so it is conservative for H-D1, but it must
be visible.

Costs per completed task on these two tasks (n=2, no inference intended):
A $0.31, A_switch $0.21, B $0.35, C1_inline $0.23, D $0.13. The parent picked
Sonnet for one task and (via fallback) Opus for the other.

Raw data: `results/exp05_smoke_paths/20260923-134403`, auto-backed-up to the
configured Google Drive folder.
