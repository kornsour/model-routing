"""Hidden grader: crossfade and smallco adopt the org reusable CI (exp06 stratum A)."""

import yaml

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


SHA = "9b2e4c71d0a3f5e8c6b1a2d4e7f90c3b5a8d1e26"
USES = f"Copperline/.github-private/.github/workflows/ci.yml@{SHA}"
NAMES = {
    "run-lint": "ci / Lint & format (Biome)",
    "run-typecheck": "ci / Type check",
    "run-build": "ci / Build",
}


def _stub(repo):
    path = ROOT / f"Copperline/{repo}/.github/workflows/ci.yml"
    text = path.read_text()
    return text, yaml.safe_load(text)


def _false(value):
    return value is False or str(value).strip().lower() == "false"


def _true(value):
    return value is True or str(value).strip().lower() == "true"


def _checks(inputs):
    checks = {"ci / Unit tests (Vitest)"}
    for key, name in NAMES.items():
        if not _false(inputs.get(key, True)):
            checks.add(name)
    if _true(inputs.get("security-scan", False)):
        checks.add("ci / Security scan (Semgrep)")
    if _true(inputs.get("migration-check", False)):
        checks.add("ci / DB migration check")
    return checks


def _common(repo):
    text, doc = _stub(repo)
    assert "runs-on" not in text, f"{repo}: caller stubs carry no runs-on"
    assert "inherit" not in text, f"{repo}: no secrets: inherit"
    jobs = doc["jobs"]
    assert list(jobs) == ["ci"], f"{repo}: one caller job with id ci, got {list(jobs)}"
    job = jobs["ci"]
    assert job.get("uses") == USES, f"{repo}: uses must pin .github-private main by full SHA"
    assert "steps" not in job
    line = next(l for l in text.splitlines() if "uses:" in l)
    assert line.rstrip().endswith("# main"), f"{repo}: pinned SHA needs a trailing # main"
    triggers = doc.get(True, doc.get("on"))
    assert "pull_request" in triggers and "push" in triggers, f"{repo}: keep the pull_request and push triggers"
    inputs = job.get("with") or {}
    assert str(inputs.get("node-version", "22")) == "22"
    return inputs


def test_crossfade_stub():
    inputs = _common("crossfade")
    assert _false(inputs.get("run-typecheck", True)), "crossfade has no typecheck: run-typecheck: false"
    assert not _false(inputs.get("run-lint", True))
    assert inputs.get("lint-command") == "pnpm lint", "crossfade lints with pnpm lint, not Biome's pnpm check"
    assert not _false(inputs.get("run-build", True))


def test_smallco_stub():
    inputs = _common("smallco")
    assert _false(inputs.get("run-lint", True)), "smallco has no lint step: run-lint: false"
    assert not _false(inputs.get("run-typecheck", True))
    assert inputs.get("typecheck-command") == "pnpm typecheck"
    assert not _false(inputs.get("run-build", True))


def test_report_check_mapping_matches_the_stubs():
    data = report_json()
    for repo, ruleset in (("crossfade", 21612243), ("smallco", 21612244)):
        _, doc = _stub(repo)
        expected = _checks(doc["jobs"]["ci"].get("with") or {})
        row = data["repos"][repo]
        assert set(row["checks_after"]) == expected, f"{repo}: reported {row['checks_after']}, stub emits {sorted(expected)}"
        assert int(row["ruleset_id"]) == ruleset


def test_report_property_ruleset_answer():
    data = report_json()
    assert data["property_ruleset_satisfied"] == {"crossfade": False, "smallco": False}
