---
title: Cross-package dependency audit before splitting the monorepo
terse: Audit which platform packages each package really imports at runtime, against what their pyproject files declare, and report in ANSWER.json.
repo: platform
parent: platform
allowed: ["ANSWER.json"]
category: investigation
tags: [read-only, investigation, dependencies]
stratum: D
max_turns: 40
harvest_shape: "read-only inventory across several repos with a fixed report format and traps called out (harvested #17: sweep rulesets read-only)"
authorship: "Brief drafted from the shape of harvested read-only dispatches by Claude Opus 5.5; fixture, answer key and reference answer by Claude Opus 5.5 (same family as the models under test)."
---
READ-ONLY. Do not modify any file. The only file you may create is `ANSWER.json` at the repo root.

We are about to split the `platform` monorepo (current directory) into three separately published packages: `orchestra`, `toolbelt` and `ledger` (under `packages/`). Before we do, I need a precise picture of how they depend on each other, because after the split a dependency that is not declared in a package's `pyproject.toml` becomes an import error in production.

Only consider the three platform packages as dependencies (ignore the standard library), and only their source trees (`packages/*/src`), not tests. A **runtime import** is one executed when a module is imported or when its functions run; imports that only happen under `if TYPE_CHECKING:` do not count. A **private import** is an import of an `_`-prefixed name from another platform package.

Answer in `ANSWER.json`, exactly this shape (lists sorted):

```json
{
  "runtime_imports": {"ledger": [], "orchestra": [], "toolbelt": []},
  "declared": {"ledger": [], "orchestra": [], "toolbelt": []},
  "undeclared": {"ledger": [], "orchestra": [], "toolbelt": []},
  "unused_declared": {"ledger": [], "orchestra": [], "toolbelt": []},
  "private_imports": ["<importing module>:<package.module.name>"],
  "type_checking_only": ["<importing module>:<package.module.name>"],
  "orchestra_cli_works_with_declared_deps_only": true
}
```

- `runtime_imports`: the other platform packages each package imports at runtime.
- `declared`: the platform packages listed in each package's `pyproject.toml` `dependencies`.
- `undeclared`: runtime imports missing from `declared`; `unused_declared`: declared but never imported at runtime.
- `private_imports` and `type_checking_only`: one entry per imported name, e.g. `"ledger.store:orchestra.model._thing"` (importing module by dotted name).
- `orchestra_cli_works_with_declared_deps_only`: would `orchestra run some-pipeline.json` work in an environment that has `orchestra` and only its declared dependencies installed?
