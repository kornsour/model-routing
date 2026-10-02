"""Hidden grader: FAQ fact-check (exp06 stratum D)."""

import json
from pathlib import Path

import pytest

KEY = {"F1": True, "F2": True, "F3": False, "F4": False, "F5": True,
       "F6": False, "F7": True, "F8": True, "F9": False, "F10": False}


@pytest.fixture(scope="module")
def answer():
    return json.loads((Path.cwd() / "ANSWER.json").read_text())


@pytest.mark.parametrize("claim", sorted(KEY))
def test_claim(answer, claim):
    assert answer[claim] is KEY[claim]
