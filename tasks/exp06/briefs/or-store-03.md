---
title: Move orchestra's run store to format v3 and read the archive's v1 files
terse: Implement orchestra run-store format v3 with v1/v2 migration per docs/run-format.md.
repo: orchestra
allowed: ["src/orchestra/store.py", "tests/*.py"]
category: migration
tags: [migration, serialization, spec-compliance]
---
Two problems with `src/orchestra/store.py`, both blocking the dashboard archive project:

1. The archive has thousands of runs written by orchestra 0.5 in the old version 1 layout, and `store.loads` refuses anything that isn't version 2.
2. Archived runs are big, and last week a truncated file loaded "successfully" with half its events missing. The platform team has specified a version 3 layout with column-wise events and a checksum.

`docs/run-format.md` documents all three versions and exactly how reading and migration must behave, including how v1's status and event names map to today's, what to fill in for information v1 didn't record, how the v3 checksum is computed, and which malformed inputs must be rejected. Please implement it in `src/orchestra/store.py`:

- `dumps(result)` writes version 3 (sorted keys, indent 2), and `save`/`load` keep working on files.
- `loads(text)` reads versions 1, 2 and 3 and returns a `RunResult` whose `runs` are in the right order (run order for v2/v3, by name for v1) and whose events and job states match what was stored.
- `migrate(doc)` is a new public function: it upgrades a parsed document of any supported version to a version 3 document with a valid checksum, one version step at a time, without modifying the document it was given; a version 3 document comes back unchanged.
- Every rejection listed in the doc (and invalid JSON) is a `ValueError`; the checksum failure's message should mention the checksum.

The `RunResult`, `JobRun` and `Event` types in `model.py` stay as they are; this is only about the storage layer. Keep `python -m pytest -q` green (the existing round-trip test must still pass) and add tests, including one that loads the v1 example from the doc.
