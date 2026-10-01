# toolbelt

Stdlib-only helpers shared by the deploy tooling, the job runner and the
billing exporter. Every module is self-contained; import what you need.

| module | what it does |
|---|---|
| `toolbelt.text` | slugs, truncation, whitespace normalisation |
| `toolbelt.numbers` | clamping, percentage formatting, safe division |
| `toolbelt.iterutil` | chunking, pairwise, stable de-duplication |

Run the tests with `python -m pytest -q` from this directory. No install step
is needed: `tests/conftest.py` puts `src/` on the path.

## Modules

| module | what it does |
|---|---|
| `toolbelt.backoff` | retry backoff (`Backoff`): exponential, capped, optional seeded jitter |
| `toolbelt.durations` | ISO 8601 durations |
| `toolbelt.iniconf` | INI configuration parsing |
| `toolbelt.money` | exact money: minor units, allocation, formatting |
| `toolbelt.iterutil`, `toolbelt.numbers`, `toolbelt.text` | small helpers |
