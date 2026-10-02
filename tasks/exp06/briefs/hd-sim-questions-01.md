---
title: Why did the simulated nightly take 53 minutes?
terse: Investigate the simulated nightly pipeline run and answer ops' questions in ANSWER.json.
repo: orchestra
allowed: ["ANSWER.json"]
category: investigation
tags: [read-only, investigation, scheduling]
stratum: D
max_turns: 40
harvest_shape: "read-only investigation with a fixed report format and an explicit no-edits rule (harvested #3/#7/#20: investigate and report only)"
authorship: "Brief drafted from the shape of harvested read-only dispatches by Claude Opus 5.5; fixture, answer key and reference answer by Claude Opus 5.5 (same family as the models under test)."
---
READ-ONLY INVESTIGATION. Do not modify any file in the repository. The only file you may create is `ANSWER.json` at the repo root.

Ops simulated tonight's nightly pipeline with `examples/nightly.json` before the warehouse migration and has questions about the result. The scheduling rules are documented in the `orchestra.scheduler` module docstring; you may run the simulator as much as you like (the package lives under `src/`, so put that on `sys.path`, e.g. `python -c "import sys; sys.path.insert(0, 'src'); from orchestra.cli import main; main(['run', 'examples/nightly.json'])"`).

Answer in `ANSWER.json`, exactly this shape (numbers as JSON numbers, simulated minutes):

```json
{
  "extract_orders_first_start": 0,
  "extract_inventory_attempts": 0,
  "extract_inventory_retry_times": [0, 0],
  "upstream_failed_jobs": ["..."],
  "notify_reason": "...",
  "makespan": 0,
  "load_inventory_ready_at": 0,
  "load_inventory_wait": 0,
  "makespan_with_4_warehouse": 0
}
```

- `extract_orders_first_start`: when `extract_orders` first starts.
- `extract_inventory_attempts`, `extract_inventory_retry_times`: its attempt count and the `retry_at` time of each retry, in order.
- `upstream_failed_jobs`: every job that ends `upstream_failed`, sorted by name; `notify_reason`: the `reason` recorded for `notify`.
- `makespan`: the run's makespan as the scheduler defines it.
- `load_inventory_ready_at`: the time at which every dependency of `load_inventory` had succeeded; `load_inventory_wait`: how long after that it actually started.
- `makespan_with_4_warehouse`: the makespan with the warehouse capacity raised to 4, everything else unchanged.
