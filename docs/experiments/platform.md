# Local routing experiment platform

Start with `make lab`, then open http://127.0.0.1:8765. The static dashboard
and existing CLI remain available. No dependencies or cloud resources were added.

The UI supports two same-vendor tracks, light/dark/system themes, expandable
help, saved plans, estimation, asynchronous sequential runs, and persisted
job status. Configure vendor, task sample size, trials, execution order,
quality floor, permitted quality loss, savings target, and run budget.
Simulation is the default and makes no provider calls. Uncheck it to explicitly
launch a real run after estimating. A budget is a post-call stop threshold,
not a hard spending cap: the final in-flight call can overshoot.

The platform has three report pages: the overview and experiment lab, a
selected-run report, and a study-design/readiness review. Quality changes and
cost savings use deterministic 95% task-clustered bootstrap intervals. All
trials for a sampled task stay together, because repeated trials measure model
variation and are not independent workload observations. The intervals
describe sensitivity to the selected benchmark tasks; they do not make the
task set representative of company work.

Plans and job state live in `results/index.sqlite` alongside the existing
run/outcome/call index. JSONL remains the source of truth for measurements.
**Do not delete the database to rebuild the index:** it now contains saved
plans that cannot be recovered from result files. Indexing preserves the jobs
table. On restart, running jobs become interrupted; inspect their partial
results and estimate a new run. Runs are never silently resumed.

## Review of the original setup

The original harness has valuable primitives: per-call usage, resolved model
IDs, router overhead, deterministic graders, sequential execution and answer
inspection. Its current live baseline is a five-task easy-only smoke test,
not evidence for a company rollout. Main issues addressed here:

- Read-only dashboard: added local estimate/save/launch workflow.
- Incomplete baseline set in routing experiments: both presets include small,
  middle, strong and strong-low-effort baselines in the same run.
- Cross-vendor emphasis: each new experiment uses exactly one vendor.
- Cost-only interpretation: paired quality and cost gates plus new failures
  relative to the strong baseline. Incomplete comparisons never qualify.
- Answer-key access: privileged label and grader cascades occur only in the
  research preset and are labeled as reference strategies.
- Fragile SQLite call attribution: use exact sequence IDs from nested outcome
  records, rather than stopping at a matching cumulative dollar amount. Legacy
  records without nested calls retain the old compatibility fallback.
- Uncounted interrupted-call spend: run totals now include all recorded calls,
  including calls not attached to a completed outcome.
- Hidden provider work: Claude Code may make an auxiliary Haiku call even when
  Sonnet or Opus is requested. The harness uses the CLI's per-model list-cost
  ledger when present, and the report shows the otherwise invisible difference
  as provider-helper-model cost instead of undercounting it.
- Reproducibility: new runs snapshot task-file hashes and price rows. Cost
  charts use the recorded prices when available; old charts retain current
  price fallback. New presets use explicit model IDs rather than aliases.
- Auditability: new runs also record the selected task manifest and hashes for
  every referenced context document, so a task-file hash cannot hide changed
  shared source material.
- CLI estimate ignored `--sample`: it now honors it. The UI defaults to evenly
  spaced sampling; this is reproducible, not randomized or population-weighted.

## Track 1: adoption evidence

Anthropic: Haiku 4.5, Sonnet 5, Opus 5. OpenAI: GPT-5.6 Luna, Terra, Sol.
The strong baseline uses the provider's default effort, with a separate low
variant; it is not a test of every possible maximum-effort setting.

Presets also run a heuristic, a small-model classifier with its cost charged,
and a three-tier self-confidence cascade. All comparisons are task/trial-paired
within a single run. Default exploratory gates: 95% pass rate, no more than
2 percentage points below strong, and at least 10% less total cost. These are
editable policy choices, not universal scientific thresholds. Cost per correct
task, latency, failures, cache use, and answers remain visible in the report.

Before a leadership decision:

1. Freeze a representative workload, rubric, and acceptable category-specific
   failure rates. Separate routine work from high-consequence work.
2. Grade exact tasks deterministically. For writing and synthesis, use blinded
   human review of correctness, completeness, groundedness and usefulness.
   Regex/keyword checks cannot substitute for this. Human review is not yet
   implemented in the platform.
3. Tune on development data and evaluate once on held-out task families.
   Repeated trials measure variation, not independent workload coverage.
4. Report uncertainty clustered by task, category regressions and tail latency.
   The platform reports task-clustered bootstrap intervals. They are
   descriptive for the benchmark and are not a significance or population
   claim.
5. Test actual native-product workflow quality and contract economics. CLI
   scaffolding, cache behavior, and API list prices are proxies. This platform
   cannot inject a router into Cowork or ChatGPT Work.

Model references checked 2026-09-18:
[Haiku](https://www.anthropic.com/claude/haiku),
[Sonnet](https://www.anthropic.com/claude/sonnet),
[Opus](https://www.anthropic.com/claude/opus),
[GPT-5.6](https://openai.com/index/gpt-5-6/).
Use the recorded resolved model on each call to audit actual availability.

## Track 2: make routing more useful

Available now: the same baselines, classifier overhead, effort reduction,
confidence cascades, difficulty-label reference and answer-key cascade.
Difficulty labels are subjective; they are not a mathematical upper bound.
The answer-key cascade represents privileged verification, not a deployable
checker. Keep these references separate from product-ready comparisons.

Next research experiments, not implemented training features:

| Experiment | Intervention | Required evaluation |
| --- | --- | --- |
| Learned success predictor | Train a cheap router on per-model successes, not subjective difficulty | Task-family train/validation/test split; calibration and routing cost |
| Calibrated abstention | Predict risk and escalate when predicted error exceeds a threshold | Threshold selected only on validation; false acceptance on test |
| Specialist distillation | Train a small model for a narrow work category | Unseen sources/templates; specialist and generalist baselines |
| Independent verifier | Check evidence or constraints without the answer key | Verifier false positives, latency and cost included |
| Adaptive reasoning | Allocate effort before escalating model size | Same quality gate, task-paired cost including repeated work |

For training, include data labeling, training, verification and serving costs.
Break-even requests = incremental fixed training cost / per-request net saving,
only when net saving is positive and the quality gate passes. Vendor model
internals cannot be changed through the current CLI providers; architecture
research needs a provider exposing trainable models and reproducible checkpoints.

## Dispatch routing lab

`make app`, or double-click `scripts/Model Routing Lab.command`, launches the
server and opens the browser straight to `/dispatch` (equivalent to
`model-routing serve --open --page dispatch`). It is the operator-facing UI
for the agentic, dispatch-time routing experiments in
`docs/experiments/dispatch-routing.md` and `experiments/agentic/*.toml` — a
separate surface from the single-shot lab at `/` (the two link to each
other). It uses the `claude` / `codex` CLI logins already on the machine;
nothing is entered into the page.

Steps in the page:

1. **Choose track** — pick Claude or ChatGPT (whichever CLI is signed in;
   the other is disabled with a one-line fix hint) and a config. "Pilot"
   presets a small, cheap sample to size variance; "Full" loads the
   pre-registered sample, trial count and policy set for the confirmatory
   run.
2. **Size the run** — task sample, trials, which policies to include, and a
   budget in dollars.
3. **Estimate, simulate, or run** — "Estimate" and "Simulate" never call a
   provider. "Run for real" is disabled until you estimate, and opens a
   confirm dialog stating the dollar estimate, the budget cap, and that it
   bills the selected subscription at API rates. The budget is a
   post-session stop, not a hard cap: the in-flight session when the budget
   is crossed can still overshoot it.

Live progress (cells done, spend vs. budget, current cell, elapsed time, a
cancel button) polls every two seconds while a run is active. Selecting a
finished run shows a verdict card for the primary hypothesis (H-D1), a
cost-per-completed-task-vs-pass-rate chart, a policy table, and cards for
the secondary hypotheses, with a "copy summary as Markdown" button.
Simulated runs are always marked with a banner.

Only one dispatch run executes at a time; job state is written to
`results/dispatch_jobs/<id>.json` (not `results/index.sqlite`), so history
survives a server restart. A job still `running` when the server starts is
marked `interrupted`; it is never silently resumed.

## Data safety

`results/` is git-ignored and is the only place the JSONL call/outcome logs,
`meta.json`, and `summary.md/json` for a run live. `results/index.sqlite`
(run/outcome/call index, plus saved single-shot plans and dispatch job
history) and `results/dispatch_jobs/*.json` sit alongside it. **If this
checkout is a git worktree, deleting the worktree deletes `results/` with
it** — nothing under it is tracked by git, so there is no other copy.

`src/model_routing/backup.py` copies finished real runs somewhere durable:

- **Auto-backup.** After a non-simulated run finishes (dispatch or
  single-shot; any end state — done, over-budget, cancelled, or failed), the
  CLI (`model-routing run` / `dispatch-run`) and the web job managers
  (`platform.Lab`, `dispatch.web.DispatchLab`) call `backup.auto_backup`.
  Simulated (`--fake`) runs are never backed up — there is nothing to lose.
  A backup failure is logged loudly but never crashes the run or discards
  the local data; the run's own files in `results/` are always the fallback.
- **Where backups land.** By default, a detected Google Drive for desktop
  folder: `~/Library/CloudStorage/GoogleDrive-<account>/My Drive/
  model-routing-backups/<experiment>/<stamp>/`, auto-detected only when
  exactly one `GoogleDrive-*` folder exists under `~/Library/CloudStorage`
  (otherwise configure one explicitly). Each run's backup includes its raw
  files (JSONL, `meta.json`, `config.toml`, `summary.*`; sandbox working
  copies are skipped), a standalone `report.html`, and a `manifest.json` of
  sha256 hashes used to verify the copy and detect drift. The human-facing
  exports go to a flat, chronologically sorted `<backup_dir>/Reports/`
  folder: `2026-09-22_23-39-41_exp05_pilot_report.html` and
  `2026-09-22_23-39-41_exp05_pilot.zip` (run start time, local; simulated
  runs end in `_simulated`, estimates in `_estimate`).
  `results/index.sqlite` is snapshotted via SQLite's own backup API into
  `<backup_dir>/_index/` (last 10 kept), and `results/dispatch_jobs/` is
  mirrored into `<backup_dir>/_dispatch_jobs/`.
- **Settings** persist outside the repo at
  `~/.config/model-routing/settings.json` (`backup_dir`, `auto_backup`), so
  they too survive a deleted worktree. `MODEL_ROUTING_BACKUP_DIR` overrides
  the configured directory (used by tests).
- **Export.** `model-routing export RUN [--out DIR]`, the dispatch page's
  per-run "Download .zip", and the lab overview's run history both produce
  the same timestamped `<YYYY-MM-DD_HH-MM-SS>_<experiment>.zip` (when the run
  started, local time; unique per run and sorts by date): every run file plus
  `report.html` and a `README.txt` explaining how to restore it. Use this to
  keep a report in Google Drive by hand, or to hand a run to someone else.
- **Restore.** `model-routing restore BACKUP_DIR` (or the dispatch page's
  "Restore from backup") copies runs present in the backup but missing from
  `results/` back in, verifies each manifest, and rebuilds the SQLite index.
  It never overwrites a local file that differs from its backup — those are
  reported as conflicts instead, left for a human to reconcile.
- **Status.** `model-routing backup-status`, `GET /api/backup/status`, and
  the per-run badge in the dispatch page's run history ("Backed up to Drive
  ✓ 2 min ago" / "Not backed up") show whether each run's backup is current.

## Limits and operation

Only one server process should use a results database. Calls within a live
experiment stay sequential. Results are indexed on finish/failure, and the UI
polls status; it does not stream in-flight token usage. Stop the server with
Ctrl-C. No automatic retry or cancellation of vendor subprocesses is provided.
The server binds to loopback and checks Host, Origin and a session token for
mutations. Do not publish or reverse-proxy this personal-login service.
