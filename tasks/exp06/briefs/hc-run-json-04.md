---
title: Machine-readable output for orchestra run
terse: Add a --json flag to `orchestra run` so the planning notebook can consume results without scraping the table.
repo: orchestra
allowed: ["src/orchestra/*", "tests/*.py", "README.md", "docs/*"]
category: feature
tags: [ambiguous, cli, interchange]
stratum: C
max_turns: 40
missing_requirement: "The JSON shape is not specified; docs/notebooks.md says the notebook parses runs with orchestra.store.loads, i.e. the version-2 run file format."
answer_key: {"question": "What should the JSON look like?", "answer": "Exactly the run file format the notebook already parses: print orchestra.store.dumps(result) (format version 2) and nothing else, so orchestra.store.loads can read the output."}
harvest_shape: "one-line feature chip naming the consumer but not the contract (harvested chip style)"
authorship: "Brief drafted from the shape of harvested chips by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
The analysts' capacity-planning notebook currently scrapes the table that `orchestra run pipeline.json` prints, and it broke when a job name got longer than the column. Please add a `--json` flag to `orchestra run` that prints the result in a machine-readable form the notebook can consume directly instead of the table. Without the flag, the output must stay exactly as it is. Add tests and keep `python -m pytest -q` green.
