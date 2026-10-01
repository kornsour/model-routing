"""Hidden grader: triage-desk capability-claims audit (exp06 stratum A, harvested brief)."""

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


EXPECTED = {
    "mcp_server": "VERIFIED",
    "rbac_enforced": "GAP",
    "audit_hash_chain": "VERIFIED",
    "approval_gate_server_side": "VERIFIED",
    "rag_data_governance": "GAP",
    "eval_gates_ci": "GAP",
    "web_ui": "VERIFIED",
    "runs_offline": "VERIFIED",
}


@pytest.mark.parametrize("capability", sorted(EXPECTED))
def test_capability(capability):
    got = norm_verdict(report_json()["capabilities"][capability])
    assert got == EXPECTED[capability], f"{capability}: {got}"


def test_open_issue_overlap():
    issues = {int(str(n).lstrip("#")) for n in report_json()["open_issues_covering_gaps"]}
    assert issues == {14}
