---
title: What will the deploy job actually render from services.ini?
terse: Work out the effective values the deploy job will render from deploy/services.ini and report them in ANSWER.json.
repo: platform
parent: platform
allowed: ["ANSWER.json"]
category: investigation
tags: [read-only, investigation, configuration]
stratum: D
max_turns: 40
harvest_shape: "read-only verification of a config change before an incident window, fixed answer format (harvested #3/#23: verify, don't assume)"
authorship: "Brief drafted from the shape of harvested read-only dispatches by Claude Opus 5.5; fixture, answer key and reference answer by Claude Opus 5.5 (same family as the models under test)."
---
READ-ONLY. Do not modify any file. The only file you may create is `ANSWER.json` at the repo root.

A change to `deploy/services.ini` goes out in tonight's deploy window, and the reviewer wants to know exactly what the deploy job will render before approving. The deploy job reads the file with `toolbelt.iniconf` (`packages/toolbelt/src/toolbelt/iniconf.py`) and calls `get(section, key)` for every key it renders. Its parsing, inheritance, comment and interpolation rules are what count, not what the file's comments claim. You may run Python against it (the package is under `packages/toolbelt/src`).

Answer in `ANSWER.json`, exactly this shape (values as the strings `get` returns):

```json
{
  "api_canary_url": "...",
  "api_canary_port": "...",
  "api_canary_log_level": "...",
  "api_banner": "...",
  "api_motd": "...",
  "worker_queue": "...",
  "worker_url": "...",
  "worker_timeout": "...",
  "api_canary_key_count": 0,
  "failing_keys": ["section:key"]
}
```

- `api_canary_key_count`: how many distinct keys `get` can resolve or attempt for section `api-canary`, counting everything it inherits (its parents and `DEFAULT`).
- `failing_keys`: every `section:key` in the file for which `get` raises, sorted.
