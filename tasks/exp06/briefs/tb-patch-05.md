---
title: Implement unified-diff application for the config-drift fixer
terse: Implement toolbelt.patching.apply_patch for single-file unified diffs.
repo: toolbelt
allowed: ["src/toolbelt/patching.py", "tests/*.py"]
category: feature
tags: [spec-compliance, text-processing, stub]
---
The config-drift fixer stores approved changes to managed config files as unified diffs (the output of `diff -u`, `git diff` or Python's `difflib.unified_diff`) and re-applies them when a host's file has drifted. We don't want to shell out to `patch(1)` on those hosts, so `src/toolbelt/patching.py` needs a real implementation of `apply_patch(text, patch, *, reverse=False) -> PatchResult`. The stub has the signature, `PatchError` (a `ValueError`) and `PatchResult(text, offsets)`.

Behaviour we need, modelled on GNU patch without fuzz:

- **Input.** `patch` is a single-file unified diff. Anything before the first `@@` line (`diff --git`, `index`, `---`/`+++` headers) is ignored. After that, each hunk starts with `@@ -OLD_START[,OLD_LEN] +NEW_START[,NEW_LEN] @@` (an omitted length means 1; anything after the second `@@` is a section label and is ignored), followed by lines starting with ` ` (context), `-` (removed) or `+` (added). A completely empty line inside a hunk is a context line whose content is empty (editors strip the trailing space). A `\ No newline at end of file` line (any line starting with `\`) means the line just before it has no trailing newline. A hunk must contain exactly the number of old-side (context + removed) and new-side (context + added) lines its header says. A second file header (`diff `, `---`, `+++`, `index ` lines) after the hunks have started, a patch with no hunks, an unrecognised line inside a hunk, a malformed header, and hunks that are out of order or overlap are all `PatchError`.
- **Placement.** Each hunk's old side (context + removed lines, including their newline status) must match a contiguous block of the current text exactly. The hunk is expected at `OLD_START` (for a hunk with `OLD_LEN` 0, which inserts, the new lines go *after* line `OLD_START`; 0 means the top), shifted by the offset at which the previous hunk actually applied. If the block is not at the expected position, search the rest of the file for it and use the match closest to the expected position (on a tie, the earlier one). A hunk may only match lines after the end of the previous hunk's block; it may not reuse or overlap lines another hunk already consumed. If no match exists, raise `PatchError` whose message names the 1-based hunk number (e.g. "hunk 2 does not apply"). Insertion-only hunks are placed at their expected position without searching, and it is an error if that position is before the previous hunk's end or past the end of the file.
- **Result.** `PatchResult.text` is the patched text; `PatchResult.offsets` lists, per hunk, the actual position minus the position its header gave, in lines (0 when it applied where the header said, 3 when three lines had been added above it). The function must not mutate anything it was given, and a failure anywhere means an exception with no partial result.
- **Newlines.** Line endings are `\n`. A file whose last line has no newline is represented faithfully: a hunk touching that line must carry the `\ No newline` marker to match it, and a hunk can add or remove the final newline through the marker. A result in which a line without a newline is followed by another line is an error.
- **Reverse.** `reverse=True` applies the patch backwards (swapping the roles of `-` and `+` and of the old/new header ranges), so `apply_patch(apply_patch(a, p).text, p, reverse=True).text == a`.
- Patches that create a file (`@@ -0,0 +1,N @@` on empty text) or delete all of its content (`@@ -1,N +0,0 @@`) must work.

Anything `difflib.unified_diff` produces (with any context size, including 0) must round-trip. Add tests; keep `python -m pytest -q` green; only change `src/toolbelt/patching.py` and the tests.
