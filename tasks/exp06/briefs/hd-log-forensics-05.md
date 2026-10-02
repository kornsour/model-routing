---
title: Week-in-review from the runner logs
terse: Read last week's runner logs and answer the ops review questions in ANSWER.json.
repo: orchestra
allowed: ["ANSWER.json"]
category: investigation
tags: [read-only, investigation, logs, data]
stratum: D
max_turns: 40
harvest_shape: "read-only evidence gathering from logs and stored data for a decision, with the answer format fixed (harvested #12/#25: work from what the logs retain)"
authorship: "Brief drafted from the shape of harvested read-only dispatches by Claude Opus 5.5; fixture logs (generated from orchestra simulations), answer key and reference answer by Claude Opus 5.5 (same family as the models under test)."
---
READ-ONLY. Do not modify any file. The only file you may create is `ANSWER.json` at the repo root.

Monday's ops review covers last week (1-7 September). The runner's logs are in `logs/runner-YYYY-MM-DD.log`, one line per event:

```
<UTC timestamp> run=<run id> pipeline=<name> event=run_start
<UTC timestamp> run=<run id> pipeline=<name> job=<job> event=start attempt=<n> warehouse_in_use=<used>/<capacity>
<UTC timestamp> run=<run id> pipeline=<name> job=<job> event=<success|retry|fail> attempt=<n>
<UTC timestamp> run=<run id> pipeline=<name> job=<job> event=upstream_failed
<UTC timestamp> run=<run id> pipeline=<name> event=run_end status=<success|failed>
```

`warehouse_in_use` on a `start` line counts the units held right after that job started. A run can span midnight, so one run's lines can be in two files. You may run Python (`python -c ...`, or a throwaway script you delete before you finish); only `ANSWER.json` may remain.

Answer in `ANSWER.json`, exactly this shape:

```json
{
  "sla_breaches": ["<run id>"],
  "failed_runs": ["<run id>"],
  "median_nightly_minutes": 0,
  "most_retried_job": {"job": "...", "retries": 0},
  "load_orders_attempt_minutes": 0,
  "runs_with_upstream_failures": 0,
  "first_warehouse_saturation": "<UTC timestamp as in the logs>"
}
```

- `sla_breaches`: `nightly` runs that took longer than 240 minutes from `run_start` to `run_end`, sorted.
- `failed_runs`: runs whose `run_end` status is `failed`, sorted.
- `median_nightly_minutes`: the median `nightly` run duration (`run_start` to `run_end`), in minutes.
- `most_retried_job`: the job with the most `retry` events over the week, and that count.
- `load_orders_attempt_minutes`: the total minutes `load_orders` attempts ran (each attempt from its `start` to the `success`, `retry` or `fail` line that ended it), over the week.
- `runs_with_upstream_failures`: runs with at least one `upstream_failed` line.
- `first_warehouse_saturation`: the earliest `start` line reporting the warehouse pool completely in use.
