#!/usr/bin/env bash
# Rebuilds toolbelt's history for hd-git-archaeology-04: twelve commits by
# three authors and four tags, ending exactly at the fixture's files. The
# sandbox's single commit is replaced by this history.
set -euo pipefail
python3 - <<'PY'
import os
import subprocess
from pathlib import Path

final = {p.as_posix(): p.read_text() for p in Path(".").rglob("*") if p.is_file() and ".git" not in p.parts}
AUTHORS = {"ana": ("Ana Ortiz", "ana@toolbelt.example"), "ben": ("Ben Kahale", "ben@toolbelt.example"),
           "chris": ("Chris Ito", "chris@toolbelt.example")}
step = [0]


def git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True, text=True, env=ENV)


ENV = dict(os.environ)


def commit(who, message, files):
    step[0] += 1
    name, email = AUTHORS[who]
    date = f"2026-0{1 + step[0] // 4}-{10 + step[0]:02d}T10:00:00Z"
    ENV.update(GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_NAME=name,
               GIT_COMMITTER_EMAIL=email, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    for path, text in files.items():
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git("add", "-A")
    git("commit", "-q", "-m", message)


def tag(name):
    git("tag", "-a", name, "-m", name)


SLUG_V1 = '''"""Small text helpers."""

from __future__ import annotations

import re

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(value: str, sep: str = "-") -> str:
    """Lower-case slug: runs of anything else collapsed to ``sep``."""
    return _SLUG_STRIP.sub(sep, value.lower()).strip(sep)
'''
TRUNC_V1 = '''

def truncate(value: str, width: int, ellipsis: str = "...") -> str:
    """Cut ``value`` to ``width`` characters and mark the cut."""
    if len(value) <= width:
        return value
    return value[:width] + ellipsis
'''
NUM_V1 = '''"""Numeric helpers."""

from __future__ import annotations


def clamp(value: float, lo: float, hi: float) -> float:
    if lo > hi:
        raise ValueError("lo > hi")
    return max(lo, min(hi, value))
'''
NUM_V2 = NUM_V1 + '''

def safe_div(num: float, den: float, default: float = 0.0) -> float:
    return default if den == 0 else num / den


def pct(part: float, whole: float, digits: int = 1) -> str:
    """``pct(1, 3) == '33.3%'``."""
    return f"{part / whole * 100:.{digits}f}%"
'''
text_final = final["src/toolbelt/text.py"]
truncate_final = text_final[text_final.index("\n\ndef truncate"):text_final.index("\n\ndef squash_ws")]
slug_final = text_final[:text_final.index("\n\ndef truncate")]

for p in list(final):
    Path(p).unlink()
git("checkout", "-q", "--orphan", "history")
git("rm", "-rq", "--cached", ".")

commit("ana", "initial toolbelt: text.slugify and numbers.clamp", {
    "src/toolbelt/__init__.py": '"""Stdlib-only helpers shared by internal services."""\n\n__version__ = "0.1.0"\n',
    "src/toolbelt/text.py": SLUG_V1, "src/toolbelt/numbers.py": NUM_V1,
    "tests/conftest.py": final["tests/conftest.py"]})
commit("ben", "feat(text): truncate", {"src/toolbelt/text.py": SLUG_V1 + TRUNC_V1})
commit("ana", "feat(numbers): safe_div and pct", {"src/toolbelt/numbers.py": NUM_V2})
tag("v0.1.0")
commit("chris", "feat(iterutil): chunked and unique", {"src/toolbelt/iterutil.py": final["src/toolbelt/iterutil.py"]})
commit("ben", "fix(text): truncate counts the ellipsis in the width", {"src/toolbelt/text.py": SLUG_V1 + truncate_final + "\n"})
tag("v0.2.0")
commit("ana", "fix(numbers): pct reports n/a for a zero whole", {"src/toolbelt/numbers.py": final["src/toolbelt/numbers.py"]})
commit("chris", "feat(text): fold accents in slugify", {"src/toolbelt/text.py": slug_final + truncate_final + "\n"})
commit("ben", "feat(text): squash_ws", {"src/toolbelt/text.py": text_final})
tag("v0.3.0")
commit("ana", "docs: README module table", {"README.md": final["README.md"]})
commit("chris", "chore: pyproject metadata", {"pyproject.toml": final["pyproject.toml"]})
commit("ben", "test: basics for every helper", {"tests/test_basics.py": final["tests/test_basics.py"]})
commit("ana", "release: 0.4.0", {"src/toolbelt/__init__.py": final["src/toolbelt/__init__.py"]})
tag("v0.4.0")

for path, text in final.items():
    assert Path(path).read_text() == text, f"history does not end at the fixture: {path}"
git("branch", "-D", "main")
git("branch", "-m", "main")
PY
