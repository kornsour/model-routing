---
title: Size limits in the retention policy
terse: Let the artifact retention policy take a max_size like "500MB" or "2GiB".
repo: toolbelt
allowed: ["src/toolbelt/*", "tests/*.py", "config/*", "README.md"]
category: feature
tags: [ambiguous, parsing, units]
stratum: C
max_turns: 40
missing_requirement: "Whether an SI suffix (KB, MB, GB) means powers of 1000 or 1024 is not stated; the format_size docstring in toolbelt.numbers states the convention."
answer_key: {"question": "Does MB mean 10^6 or 2^20 bytes?", "answer": "Follow the convention in format_size's docstring: SI suffixes (KB, MB, GB, TB) are powers of 1000; IEC suffixes with the i (KiB, MiB, GiB, TiB) are powers of 1024. A bare number or a B suffix is bytes."}
harvest_shape: "small config feature request with one example value and no unit definition (harvested chip style)"
authorship: "Brief drafted from the shape of harvested chips by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
The artifact store filled its disk again over the weekend. Age-based retention isn't enough: a single pipeline can write 300 GB in a day. Ops wants a size cap alongside the age cap.

Please add `toolbelt.numbers.parse_size(text: str) -> int` (bytes) and teach `toolbelt.retention.load` to read an optional `max_size` (e.g. `max_size = 500MB`, or `max_size = 2GiB` from the people who think in binary) into `Policy.max_size_bytes` (`None` when absent). Garbage like `500 parsecs` should be a `ValueError`. Add an example to `config/retention.example.ini`, tests for both functions, and keep `python -m pytest -q` green.
