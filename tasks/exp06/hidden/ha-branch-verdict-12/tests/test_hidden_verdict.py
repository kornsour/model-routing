"""Hidden grader: single-branch verdict, folio-site feat/aws-static-site (exp06 stratum A)."""

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


def _paths(values):
    return {p.removeprefix("./") for p in values}


def test_verdict_is_needs_decision():
    assert norm_verdict(report_json()["verdict"]) == "NEEDS-DECISION"


def test_behind_count():
    assert int(report_json()["behind"]) == 27


def test_absent_files_split_correctly():
    absent = report_json()["absent_from_main"]
    application = _paths(absent.get("application", []))
    infra = _paths(absent.get("infra", []))
    assert {"site/contact.html", "site/js/contact-form.js"} <= application, "the contact page would be lost"
    assert {"infra/s3-site.tf", ".github/workflows/aws-static-site.yml"} <= infra
    assert not ({"infra/s3-site.tf", ".github/workflows/aws-static-site.yml"} & application)


def test_read_only():
    assert git("log", "-1", "--format=%s", "feat/aws-static-site") == "feat: host on S3 + CloudFront, add contact page"
    assert git("log", "-1", "--format=%s", "main") == "content: refresh about page"
