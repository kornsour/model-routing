"""Hidden grader: single-branch verdict, packlight feat/aws-staging (exp06 stratum A)."""

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


def test_verdict_is_delete():
    assert norm_verdict(report_json()["verdict"]) == "DELETE"


def test_behind_count():
    assert int(report_json()["behind"]) == 11


def test_absent_files_split_correctly():
    absent = report_json()["absent_from_main"]
    infra = {p.removeprefix("./") for p in absent.get("infra", [])}
    assert {"sst.config.ts", "sst-env.d.ts", ".github/workflows/aws-staging.yml"} <= infra
    assert not absent.get("application"), "no application code is absent from main"


def test_read_only():
    assert git("log", "-1", "--format=%s", "feat/aws-staging") == "feat: AWS staging environment via SST"
    assert git("log", "-1", "--format=%s", "main") == "test: share link (#44)"
