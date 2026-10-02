---
title: Human-readable durations in runner log lines
terse: Make the Python runner's log lines print durations the way the old runner did.
repo: toolbelt
allowed: ["src/toolbelt/*", "tests/*.py", "README.md"]
category: feature
tags: [ambiguous, format, logs]
stratum: C
max_turns: 40
missing_requirement: "The exact duration format (which units, how many, rounding, zero) is not stated; docs/runner-logs.md has the legacy runner's samples and rounding note."
answer_key: {"question": "What exact format should the durations use (units, how many units, rounding, zero)?", "answer": "Exactly what the legacy runner printed (docs/runner-logs.md): from whole seconds rounded down, the largest non-zero unit of d/h/m/s plus the next smaller unit even when it is zero (1d 0h, 1m 0s); under a minute is just seconds (45s); zero is 0s."}
harvest_shape: "small, self-contained change that must stay compatible with an existing consumer (harvested #14: copy change with an e2e assertion that must match exactly)"
authorship: "Brief drafted from the shape of harvested chips by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
We're cutting the job runner over from the old Go binary to the Python one this week, and the first night of logs broke the on-call alerts: the Python runner writes `took=7384.2s` where the old one wrote a human-readable duration like `2h 3m`, and the log shipper's pattern no longer matches.

Please add `toolbelt.runlog.humanize(seconds: float) -> str` and use it in `toolbelt.runlog.format_line` so that the lines the Python runner writes are indistinguishable from the old runner's. The log shipper and the alert rules must not need to change.

Add tests for `humanize` and the updated `format_line`, add the module to the README table, and keep `python -m pytest -q` green.
