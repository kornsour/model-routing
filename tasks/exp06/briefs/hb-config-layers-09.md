---
title: Layered ledger configuration with provenance and redaction
terse: Add merge/set to toolbelt.iniconf and build ledger's layered config (defaults, system, project, env, CLI) with per-key provenance, secret-safe dumps and CLI integration.
repo: platform
parent: platform
allowed: ["packages/toolbelt/*", "packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [long-horizon, multi-package, configuration, security]
stratum: B
max_turns: 80
harvest_shape: "config-store feature spanning a shared library and an app, with a never-display-secrets rule and a must-fail-loudly guard (harvested #1: config store + safeStorage replaces .env)"
authorship: "Brief drafted from the shape of harvested dispatch #1 by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Every `ledger` command takes its file paths as flags, and the runner host, the analysts' laptops and CI each pass different ones. We want one layered configuration with a clear answer to "where did this value come from?", and we want it safe to paste into a ticket. You are in the `platform` monorepo (current directory); `python -m pytest -q` runs every suite. Read `packages/toolbelt/src/toolbelt/iniconf.py` first: section inheritance (`[child : parent]`), `DEFAULT`, and `${section:key}` interpolation already exist and are well tested.

## toolbelt.iniconf

1. `Config.set(section, key, value)` — sets a raw (uninterpolated) value, creating the section if needed; keys are case-insensitive like everywhere else in the module.
2. `merge(*configs) -> Config` — a new config where, key by key, a later config overrides an earlier one (`DEFAULT` included). A section's parent is taken from the **last** config that declares one for it. Values are merged raw, so interpolation is resolved against the merged result: a project file may reference a key that only the system file defines. The inputs are not modified. A layer may declare `[child : parent]` where `parent` only exists in another layer, so `parse` gains a keyword-only `require_parents=True`; layers are parsed with `require_parents=False`, and `merge` instead checks that every parent exists in the merged result (and that there is no inheritance cycle), raising `ConfigError` otherwise.
3. `Config.raw(section, key) -> tuple[str, str] | None` — public version of the existing private lookup: the raw value and the section it was found in (following parents and `DEFAULT`), or `None`. Tests for all three in `packages/toolbelt/tests/test_iniconf.py`.

## ledger.config (new module)

4. Layers, lowest to highest precedence:
   1. built-in defaults: `[paths] history = history.jsonl`, `inflight = inflight.json`, `rates = rates.json`;
   2. a system file (`--system-config`), optional;
   3. a project file (`--config`, default `ledger.ini` in the current directory if it exists);
   4. environment variables `LEDGER__<SECTION>__<KEY>` (double underscores; section and key are lower-cased; other variables are ignored);
   5. command-line overrides `--set section.key=value` (repeatable; the first `.` separates section from key).
5. `load_config(system=None, project=None, env=None, overrides=()) -> LedgerConfig` (`env` defaults to `os.environ`; `overrides` is a sequence of `"section.key=value"` strings; a malformed one is a `ValueError`). `LedgerConfig.get(section, key)` returns the interpolated value; `LedgerConfig.provenance(section, key)` returns where the **raw** value came from: `"default"`, `"system:<path>"`, `"project:<path>"`, `"env:<VARIABLE>"` or `"cli:<section>.<key>"`. A key found through section inheritance or `DEFAULT` reports the layer that supplied that raw value.
6. **Secrets.** A key is secret when its name contains `password`, `secret` or `token`, or ends with `key` (case-insensitive). `LedgerConfig.dump() -> str` renders every section (sorted, `DEFAULT` excluded) and every key visible in it (sorted) as `key = value  # provenance`, sections as `[name]` headers separated by a blank line, ending with a newline. A secret key's value is shown as `********`. A non-secret value whose interpolation references a secret key — directly or through other keys — is shown **raw**, with its `${...}` references intact, never interpolated. Every other value is shown interpolated.
7. **Fail loudly.** If any value fails to interpolate (unknown key, cycle), `load_config` raises `toolbelt.iniconf.ConfigError` naming it; it must not return a half-working config.

## CLI

8. Global options before the subcommand: `--config`, `--system-config`, `--set` (repeatable). Every existing `--history`, `--inflight` and `--rates` flag keeps working but now defaults to the config's `[paths]` value.
9. `ledger config show` prints `dump()`; `ledger config get SECTION.KEY` prints the value (a secret prints `********`); `ledger config why SECTION.KEY` prints the provenance. An unknown key exits 1 with a message on stderr.

## Constraints

- Stdlib only; ledger must use the public iniconf API (no `_`-prefixed names).
- Keep every existing CLI invocation working unchanged. Update the toolbelt and ledger READMEs and module docstrings.
- Tests for each package in its own `tests/`. Report back the files changed, the precedence order as implemented, and how transitive secret references are detected.
