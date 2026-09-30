---
title: Implement path globbing for the artifact uploader
terse: Implement toolbelt.globmatch.match/select (globstar, braces, classes, dotfiles, negation).
repo: toolbelt
allowed: ["src/toolbelt/globmatch.py", "tests/*.py"]
category: feature
tags: [spec-compliance, matching, performance, stub]
---
The artifact uploader takes include/exclude lists from each repo's `upload.yml`, and teams write those lists the way they write `.gitignore` and shell globs. We tried `fnmatch` and it is wrong for this (its `*` crosses directories and it has no `**` or braces). `src/toolbelt/globmatch.py` has the two signatures stubbed; please implement them to these rules.

`match(pattern, path, *, dot=False, ignore_case=False) -> bool` decides whether a relative, `/`-separated path matches a pattern. The whole path must match. An empty path never matches.

- **Segments.** Patterns and paths are compared segment by segment (split on `/`). `*` matches any run of characters within one segment (possibly empty), `?` matches exactly one character, and neither ever matches `/`.
- **Globstar.** A segment that is exactly `**` matches zero or more whole segments (`a/**/b` matches `a/b` and `a/x/y/b`; `**/*.py` matches `a.py`). A trailing `/**` matches one or more segments below its prefix, but not the prefix itself (`src/**` matches `src/a` and `src/a/b` but not `src`). `**` anywhere else (e.g. `a**b`) is just a `*`.
- **Classes.** `[abc]`, ranges `[a-z]`, negation with `[!...]` or `[^...]`. A `]` right after the opening `[` (or after the `!`/`^`) is a literal `]`; a `-` first or last is a literal `-`; a backslash inside a class escapes the next character. A class matches exactly one character and never matches `/`. A `[` with no closing `]` is a literal `[`.
- **Braces.** `{a,b,c}` expands to alternatives, which may be nested (`{a,{b,c}d}`), may be empty (`{,pre}fix`), and may contain `/` and other glob syntax (`{src,lib}/**/*.{py,pyi}`). A brace group with no comma at its top level (`{x}`) or with no closing brace is literal text, and commas outside braces are literal.
- **Escapes.** A backslash makes the next character literal (`\*`, `\{`, `\[`, `\\`); a trailing backslash is a literal backslash.
- **Dotfiles.** Unless `dot=True`, a segment that starts with `.` is only matched by a pattern segment that starts with a literal `.`: a pattern segment beginning with `*`, `?` or a class does not match it (so `*`, `*.txt`, `?env` and `[.]env` do not match `.env`, while `.*` and `.env` do), and `**` does not cross or match segments that start with `.` (`**/*.py` does not match `.venv/lib/x.py`). With `dot=True` those restrictions go away.
- **Case.** Case-sensitive unless `ignore_case=True` (which also applies to literals and classes).
- **Performance.** Patterns come from users. Matching must stay fast on adversarial input: something like `*a*a*a*a*a*a*a*a*a*a*a*b` against sixty `a`s, a chain of `**/**/**/...`, or a pattern with many brace groups must all answer in milliseconds, not hang (a naive translation to Python regular expressions backtracks exponentially here).

`select(paths, patterns, *, dot=False) -> list[str]` applies an ordered pattern list gitignore-style: each path is tested against every pattern in order, and the *last* pattern that matches decides; a pattern starting with `!` is a negation (a match excludes the path), a leading `\!` means a literal `!`. Paths that no pattern matches are excluded. Return the included paths in their input order.

Add tests. Keep `python -m pytest -q` green, and only change `src/toolbelt/globmatch.py` and the tests.
