"""Hidden grader: .github-private branch triage (exp06 stratum A, harvested brief)."""

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


TIPS = json.loads('{"agent/portfolio-static-export-tracker": "docs: portfolio static-export tracker", "chore/issue-31-analyzer-blocker": "feat(analyzer): check batch 4 for composite actions (#31)", "chore/issue-84-66-82-verification": "chore: verify #84 #66 #82 closure", "docs/aws-domain-inventory-2026-08-14": "docs(domains): add svc19.copperline.example", "docs/tailscale-key-expiry-reauth": "docs: key-expiry policy for tagged nodes", "rescue/aws-denials": "rescue: AWS denials observed during the August deploys", "work/runner-ops-51-53-70": "tools: drain a runner before maintenance (#70)"}')
EXPECTED = json.loads('{"agent/portfolio-static-export-tracker": ["DELETE"], "chore/issue-31-analyzer-blocker": ["PR"], "chore/issue-84-66-82-verification": ["DELETE"], "docs/aws-domain-inventory-2026-08-14": ["DELETE", "NEEDS-DECISION"], "docs/tailscale-key-expiry-reauth": ["PR"], "rescue/aws-denials": ["DELETE", "NEEDS-DECISION"], "work/runner-ops-51-53-70": ["NEEDS-DECISION"]}')
ISSUES = json.loads('{"chore/issue-31-analyzer-blocker": 31, "docs/tailscale-key-expiry-reauth": 47, "work/runner-ops-51-53-70": 70}')


def _branches():
    data = report_json()
    rows = data.get("branches", data)
    return {name.strip(): row for name, row in rows.items()}


@pytest.mark.parametrize("branch", sorted(EXPECTED))
def test_verdict(branch):
    rows = _branches()
    assert branch in rows, f"no verdict for {branch}"
    assert norm_verdict(rows[branch]["verdict"]) in EXPECTED[branch], (
        f"{branch}: {rows[branch]['verdict']} (expected one of {EXPECTED[branch]})"
    )


@pytest.mark.parametrize("branch", sorted(ISSUES))
def test_related_open_issue(branch):
    issue = _branches()[branch].get("open_issue")
    assert issue is not None and int(str(issue).lstrip("#")) == ISSUES[branch]


def test_read_only():
    for branch, subject in TIPS.items():
        assert git("log", "-1", "--format=%s", branch) == subject, f"{branch} was changed or deleted"
    assert git("log", "-1", "--format=%s", "main") == "chore: org config update 106"
