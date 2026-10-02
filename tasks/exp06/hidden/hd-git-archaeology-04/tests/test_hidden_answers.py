"""Hidden grader: toolbelt git archaeology (exp06 stratum D)."""

import json
import subprocess
from pathlib import Path

import pytest

KEY = {
    "truncate_fix_commit": "fix(text): truncate counts the ellipsis in the width",
    "truncate_at_v0_1_0": "abcdef...",
    "numbers_commit_count": 3,
    "pct_na_first_tag": "v0.3.0",
    "iterutil_first_tag": "v0.2.0",
    "slugify_last_author": "Chris Ito",
    "commits_v0_3_0_to_v0_4_0": 4,
}


@pytest.fixture(scope="module")
def answer():
    return json.loads((Path.cwd() / "ANSWER.json").read_text())


@pytest.mark.parametrize("key", sorted(KEY))
def test_answer(answer, key):
    got = answer[key]
    assert (int(got) if isinstance(KEY[key], int) else got) == KEY[key]


def test_repository_left_as_found():
    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()

    assert git("rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert git("log", "-1", "--format=%s") == "release: 0.4.0"
    assert git("tag").split() == ["v0.1.0", "v0.2.0", "v0.3.0", "v0.4.0"]
