"""Hidden grader: multi-repo branch triage and stale remote-tracking refs (exp06 stratum A)."""

import re

import pytest

import json
import re
import subprocess
from pathlib import Path

ROOT = Path.cwd()


def report_json():
    """The last fenced json block in REPORT.md."""
    path = ROOT / "REPORT.md"
    assert path.is_file(), "REPORT.md was not written"
    blocks = re.findall(r"```json\s*\n(.*?)```", path.read_text(), re.S)
    assert blocks, "REPORT.md has no fenced json block"
    return json.loads(blocks[-1])


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def norm_verdict(value):
    return re.sub(r"[\s_]+", "-", str(value).strip().upper())


EXPECTED = json.loads('{"trackbook:examples-and-diff-verdict-fix": ["DELETE"], "trackbook:python-client-contract": ["PR"], "crossfade:feat/m6-eval": ["NEEDS-DECISION"], "packlight:fix/nanoid-3-3-18": ["DELETE"], "ml-notes:learn": ["LEAVE-ALONE", "DELETE", "NEEDS-DECISION"]}')
ISSUES = json.loads('{"trackbook:python-client-contract": 12, "crossfade:feat/m6-eval": 29}')
TIPS = json.loads('{"ellisport/trackbook": {"examples-and-diff-verdict-fix": "fix(diff): negative change counts are invalid, not changed", "python-client-contract": "test(python): client contract, field 6"}, "Copperline/crossfade": {"feat/m6-eval": "eval(m6): case 7"}, "Copperline/packlight": {"fix/nanoid-3-3-18": "fix(deps): bump nanoid to 3.3.18 (security)"}, "Copperline/ml-notes": {"learn": "wip 6"}}')


def _key(name):
    repo, _, branch = name.strip().partition(":")
    return f"{repo.strip().rstrip('/').split('/')[-1]}:{branch.strip()}"


def _branches():
    return {_key(k): v for k, v in report_json()["branches"].items()}


def _refs():
    return {k.strip().rstrip("/").split("/")[-1]: v for k, v in report_json()["stale_refs"].items()}


@pytest.mark.parametrize("branch", sorted(EXPECTED))
def test_verdict(branch):
    rows = _branches()
    assert branch in rows, f"no verdict for {branch}"
    assert norm_verdict(rows[branch]["verdict"]) in EXPECTED[branch]


@pytest.mark.parametrize("branch", sorted(ISSUES))
def test_related_open_issue(branch):
    issue = _branches()[branch].get("open_issue")
    assert issue is not None and int(str(issue).lstrip("#")) == ISSUES[branch]


def test_mise_upstream_ref():
    ref = _refs()["mise"]
    assert ref["safe_to_prune"] is True
    assert ref["config_change_needed"] is True, "remote.upstream.fetch recreates the ref on every fetch"
    assert re.search(r"update-ref\s+-d\s+refs/remotes/origin/upstream/main|branch\s+(-r\s+-[dD]|-[dD]r|-r[dD])\s+origin/upstream/main", ref["cleanup"])


def test_binwise_canonical_ref():
    ref = _refs()["binwise"]
    assert ref["safe_to_prune"] is True
    assert ref["config_change_needed"] is False, "no configured refspec creates origin/canonical/main"
    assert re.search(r"update-ref\s+-d\s+refs/remotes/origin/canonical/main|branch\s+(-r\s+-[dD]|-[dD]r|-r[dD])\s+origin/canonical/main", ref["cleanup"])


def test_read_only():
    for repo, branches in TIPS.items():
        for branch, subject in branches.items():
            assert git("log", "-1", "--format=%s", branch, cwd=ROOT / repo) == subject, f"{repo}:{branch} changed"
    git("rev-parse", "--verify", "refs/remotes/origin/upstream/main", cwd=ROOT / "Copperline/mise")
    git("rev-parse", "--verify", "refs/remotes/origin/canonical/main", cwd=ROOT / "Copperline/binwise")
    assert "origin/upstream" in git("config", "--get-all", "remote.upstream.fetch", cwd=ROOT / "Copperline/mise")
