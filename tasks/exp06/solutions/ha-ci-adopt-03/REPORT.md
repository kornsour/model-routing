# crossfade and smallco onto the org reusable CI

Both stubs pin `.github-private` main at `9b2e4c71d0a3f5e8c6b1a2d4e7f90c3b5a8d1e26 # main`, caller job id `ci`, no `runs-on`, no `secrets: inherit`.

| repo | before | after | ruleset edit |
|---|---|---|---|
| crossfade (21612243) | `Unit tests`, `Lint`, `Build` | `ci / Unit tests (Vitest)`, `ci / Lint & format (Biome)`, `ci / Build` | replace all three contexts with the after list |
| smallco (21612244) | `ci` | `ci / Type check`, `ci / Unit tests (Vitest)`, `ci / Build` | replace `ci` with the after list |

Neither repo would satisfy the property ruleset (22285519) if it targeted them: crossfade lacks `Type check`, `Security scan (Semgrep)` and `lockfile / integrity`; smallco lacks `Lint & format (Biome)` and `Security scan (Semgrep)`. Not expressible: smallco's pnpm 9.15.0 pin (the shared workflow reads `packageManager`).

```json
{"repos": {"crossfade": {"ruleset_id": 21612243, "checks_before": ["Unit tests", "Lint", "Build"], "checks_after": ["ci / Unit tests (Vitest)", "ci / Lint & format (Biome)", "ci / Build"]},
           "smallco": {"ruleset_id": 21612244, "checks_before": ["ci"], "checks_after": ["ci / Type check", "ci / Unit tests (Vitest)", "ci / Build"]}},
 "property_ruleset_satisfied": {"crossfade": false, "smallco": false}}
```
