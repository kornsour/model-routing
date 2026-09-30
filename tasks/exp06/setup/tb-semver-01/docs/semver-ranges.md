# Version ranges in toolbelt

`toolbelt.semver` is what the deploy tooling uses to decide whether an
artifact version is allowed by a service's pin. The pins are written by
people who know npm, so the module follows npm's range semantics. This page
is the contract; where it and the code disagree, the code is wrong.

## Versions

`MAJOR.MINOR.PATCH`, optionally followed by `-PRERELEASE` and/or `+BUILD`.
Each of MAJOR, MINOR and PATCH is a non-negative integer without leading
zeros (`0` is fine, `01` is not). PRERELEASE and BUILD are dot-separated
identifiers of `[0-9A-Za-z-]`; a numeric prerelease identifier must not have
leading zeros. A leading `v` or `=` and surrounding whitespace are ignored
when parsing (`" v1.2.3 "` is `1.2.3`). Anything else is invalid.

Precedence (SemVer 2.0.0 section 11):

1. Compare MAJOR, MINOR, PATCH numerically.
2. A version with a prerelease has lower precedence than the same version
   without one (`1.0.0-rc.1 < 1.0.0`).
3. Two prereleases compare identifier by identifier, left to right:
   identifiers made only of digits compare numerically; others compare
   lexically in ASCII order; a numeric identifier is lower than a
   non-numeric one; if every identifier of the shorter list equals the
   corresponding one of the longer, the shorter list is lower
   (`1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta < 1.0.0-beta.2 < 1.0.0-beta.11 < 1.0.0-rc.1`).
4. BUILD metadata is ignored for precedence and equality.

## Ranges

A *range* is one or more *comparator sets* joined by `||`; a version
satisfies the range if it satisfies any set. A comparator set is one or
more comparators separated by whitespace; a version satisfies the set if it
satisfies every comparator in it. A set may also be a hyphen range or use
the tilde/caret/X shorthands below, which are rewritten ("desugared") into
primitive comparators first.

A primitive comparator is an operator (`<`, `<=`, `>`, `>=`, `=`, or none,
which means `=`) followed by a full version. Whitespace between an operator
and its version is allowed (`>= 1.2.3`). `~>` is accepted as a synonym for `~`.

### Partial versions and X-ranges

`x`, `X` and `*` stand for any value in a position; missing trailing
positions behave the same way (`1.2` is `1.2.x`, `1` is `1.x.x`). An empty
range string, or `*`, matches any version: it desugars to `>=0.0.0`.

| written | desugars to |
|---|---|
| `1.x`, `1.X`, `1.*`, `1` | `>=1.0.0 <2.0.0-0` |
| `1.2.x`, `1.2` | `>=1.2.0 <1.3.0-0` |
| `=1.2`, `1.2.*` | `>=1.2.0 <1.3.0-0` |

The `-0` on an upper bound is the lowest possible prerelease of that
version, so `<2.0.0-0` excludes every `2.0.0` prerelease.

With an operator, a partial version is filled in so that the comparison
still means what it says:

| written | desugars to |
|---|---|
| `>1` | `>=2.0.0` |
| `>1.2` | `>=1.3.0` |
| `>=1.2` | `>=1.2.0` |
| `<1.2` | `<1.2.0-0` |
| `<=1.2` | `<1.3.0-0` |
| `<1` | `<1.0.0-0` |
| `>=*`, `<=*`, `=*` | `>=0.0.0` |
| `<*`, `>*` | `<0.0.0-0` (matches nothing) |

### Hyphen ranges `A - B`

Inclusive on both ends: `>=A <=B`. There must be whitespace on both sides of
the hyphen. A partial `A` is filled with zeros (`1.2 - 2.3.4` is
`>=1.2.0 <=2.3.4`). A partial `B` accepts everything that starts with it:
`1.2.3 - 2.3` is `>=1.2.3 <2.4.0-0` and `1.2.3 - 2` is `>=1.2.3 <3.0.0-0`.
An X in `A` (`* - 2.0.0`) makes the lower bound `>=0.0.0`; an X in `B` makes
the range unbounded above (no upper comparator).

### Tilde `~`

Allows patch-level changes if a minor version is given, minor-level changes
if not.

| written | desugars to |
|---|---|
| `~1.2.3` | `>=1.2.3 <1.3.0-0` |
| `~1.2` | `>=1.2.0 <1.3.0-0` |
| `~1` | `>=1.0.0 <2.0.0-0` |
| `~0.2.3` | `>=0.2.3 <0.3.0-0` |
| `~0` | `>=0.0.0 <1.0.0-0` |
| `~1.2.3-beta.2` | `>=1.2.3-beta.2 <1.3.0-0` |

### Caret `^`

Allows changes that do not modify the left-most non-zero element among
MAJOR, MINOR, PATCH.

| written | desugars to |
|---|---|
| `^1.2.3` | `>=1.2.3 <2.0.0-0` |
| `^0.2.3` | `>=0.2.3 <0.3.0-0` |
| `^0.0.3` | `>=0.0.3 <0.0.4-0` |
| `^1.2.3-beta.2` | `>=1.2.3-beta.2 <2.0.0-0` |
| `^0.0.3-beta` | `>=0.0.3-beta <0.0.4-0` |
| `^1.2.x`, `^1.2` | `>=1.2.0 <2.0.0-0` |
| `^0.0.x`, `^0.0` | `>=0.0.0 <0.1.0-0` |
| `^1.x`, `^1` | `>=1.0.0 <2.0.0-0` |
| `^0.x`, `^0` | `>=0.0.0 <1.0.0-0` |

### Prereleases

A version that has a prerelease tag satisfies a comparator set only if (a)
it satisfies every comparator in the set, and (b) at least one comparator
in the set has a prerelease tag *and* the same MAJOR.MINOR.PATCH as the
version. So `1.2.3-alpha.7` satisfies `>1.2.3-alpha.3` but `3.4.5-alpha.9`
does not, even though it is greater. `include_prerelease=True` turns rule
(b) off.

## API

- `parse_version(text) -> Version`; raises `ValueError` if invalid. `Version`
  is ordered and hashable per the precedence rules; `str(v)` gives the
  canonical form without build metadata (`"1.2.3-rc.1"`).
- `normalize(range_text) -> str`: the desugared range. Comparators are
  written `<op><version>` with `=` omitted for exact matches, separated by
  one space; comparator sets are joined with `||` (no spaces). A range that
  is invalid raises `ValueError`.
- `satisfies(version, range_text, *, include_prerelease=False) -> bool`.
  An invalid *version* returns `False`; an invalid *range* raises
  `ValueError`. `version` may be a string or a `Version`.
- `max_satisfying(versions, range_text, *, include_prerelease=False)` and
  `min_satisfying(...)`: the highest / lowest satisfying version from the
  iterable, returned as the original string (or `Version`) that was passed
  in, or `None` if none match. Invalid versions in the list are skipped.
