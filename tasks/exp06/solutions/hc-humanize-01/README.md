# toolbelt

Stdlib-only helpers shared by the deploy tooling, the job runner and the
billing exporter. Every module is self-contained; import what you need.

| module | what it does |
|---|---|
| `toolbelt.text` | slugs, truncation, whitespace normalisation |
| `toolbelt.numbers` | clamping, percentage formatting, safe division |
| `toolbelt.iterutil` | chunking, pairwise, stable de-duplication |
| `toolbelt.runlog` | runner log lines, legacy-compatible durations |

Run the tests with `python -m pytest -q` from this directory. No install step
is needed: `tests/conftest.py` puts `src/` on the path.
