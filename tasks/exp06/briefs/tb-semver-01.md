---
title: Make toolbelt.semver follow the documented npm range contract
terse: Fix toolbelt's semver range matching so it agrees with docs/semver-ranges.md.
repo: toolbelt
allowed: ["src/toolbelt/semver.py", "tests/*.py"]
category: bugfix
tags: [spec-compliance, parsing, long-brief]
---
The deploy gate has been letting the wrong artifacts through. Two incidents this month:

1. A service pinned to `^0.4.2` was deployed with `0.5.1`, which has a breaking config change. npm would never have allowed that (a caret on a 0.x version only allows patch-level changes), but `toolbelt.semver.satisfies("0.5.1", "^0.4.2")` returns True.
2. A pin of `^2.3.0` picked up `3.0.0-beta.1` from the internal registry during a canary. Prereleases of a later version should never satisfy a range unless the range itself names a prerelease of that same version.

When I looked, `src/toolbelt/semver.py` is an early, simplified implementation that predates `docs/semver-ranges.md`. The doc is the contract the platform team agreed on (it mirrors npm's semantics because everyone writing pins knows npm), and the code disagrees with it in more places than the two above: prerelease ordering is lexical instead of per-identifier (so `beta.11` sorts before `beta.2`), partial versions after `>` / `<` / `<=` are filled in the wrong way, hyphen ranges with a partial upper bound are wrong, parsing accepts things the doc calls invalid, and several documented functions and options (`min_satisfying`, `include_prerelease`, `str()` canonical form, build metadata being ignored for equality) are missing or wrong.

Please bring `src/toolbelt/semver.py` fully in line with `docs/semver-ranges.md`: versions, precedence, every desugaring rule in the tables (including the `-0` upper bounds), hyphen ranges, the prerelease rule, `normalize`'s exact output format, and the API section (return types, which errors raise and which return False/None, returning the original list element from `max_satisfying`/`min_satisfying`). Treat the doc as authoritative even where you think npm does something slightly different. The deploy gate calls `satisfies`, `max_satisfying` and `normalize` (the last one is printed in the gate's audit log, so its exact format matters), and passes both strings and `Version` objects.

Keep the public names that exist today; other modules import `Version`, `parse_version`, `satisfies`, `max_satisfying` and `normalize`. Add tests covering the cases you fix. `python -m pytest -q` must stay green. Keep the change to the semver module and its tests; don't touch the doc or other modules.
