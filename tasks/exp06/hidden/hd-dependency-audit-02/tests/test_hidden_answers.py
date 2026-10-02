"""Hidden grader: dependency audit (exp06 stratum D)."""

import json
from pathlib import Path

import pytest

KEY = json.loads("""
{
  "runtime_imports": {"ledger": ["orchestra", "toolbelt"], "orchestra": ["toolbelt"], "toolbelt": []},
  "declared": {"ledger": ["orchestra", "toolbelt"], "orchestra": [], "toolbelt": []},
  "undeclared": {"ledger": [], "orchestra": ["toolbelt"], "toolbelt": []},
  "unused_declared": {"ledger": [], "orchestra": [], "toolbelt": []},
  "private_imports": ["ledger.inflight:toolbelt.durations._td"],
  "type_checking_only": ["toolbelt.text:orchestra.model.JobSpec"],
  "orchestra_cli_works_with_declared_deps_only": false
}
""")


@pytest.fixture(scope="module")
def answer():
    return json.loads((Path.cwd() / "ANSWER.json").read_text())


@pytest.mark.parametrize("key", sorted(KEY))
def test_answer(answer, key):
    got, want = answer[key], KEY[key]
    if isinstance(want, dict):
        assert {k: sorted(v) for k, v in got.items()} == want
    elif isinstance(want, list):
        assert sorted(got) == want
    else:
        assert got is want
