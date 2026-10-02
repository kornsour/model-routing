"""Hidden grader: org and personal-account ruleset sweep (exp06 stratum A, harvested brief).

The answer key was derived mechanically from gh-snapshot/ by a reference solver.
"""

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


ANSWER = json.loads('{"no_enforcement": ["Copperline/northstar-docs", "ellisport/gh-automation", "ellisport/dotfiles", "ellisport/chess-clock", "ellisport/tidy-photos", "ellisport/md-slides", "ellisport/budget-cli", "ellisport/weather-pi", "ellisport/habit-log", "ellisport/recipe-scale", "ellisport/snippets", "ellisport/lab-notes", "ellisport/cron-pal", "ellisport/zine", "ellisport/kata", "ellisport/pixel-font"], "mismatched_contexts": {"Copperline/echoform": ["ci / DB migration check"], "Copperline/ledgerline": ["ci / DB migration check"], "Copperline/routewise": ["ci / Lint (ruff)", "ci / Tests (pytest)"], "Copperline/tallyhub": ["lockfile / integrity"], "Copperline/quillstack": ["ci / Build", "ci / Lint & format (Biome)", "ci / Type check", "ci / Unit tests (Vitest)"], "ellisport/folio-site": ["deploy"], "ellisport/design-kit": ["visual-regression"]}, "strict": ["Copperline/beacon", "Copperline/relay-bot", "ellisport/folio-site", "ellisport/trackbook", "ellisport/narrator", "ellisport/ts-starter", "ellisport/design-kit"], "missing_properties": {"Copperline/northstar-docs": ["tier"], "Copperline/pantry-api": ["tier"], "Copperline/swatch": ["database"], "Copperline/harbor-sim": ["ci-managed"]}, "archived_skipped": 3, "scanned": 45}')


def _repo(name):
    return str(name).strip().lower().rstrip("/").split("/")[-1]


def _repos(values):
    return {_repo(v) for v in values}


def _mapping(values):
    return {_repo(k): {str(x).strip() for x in v} for k, v in values.items()}


def test_no_enforcement():
    assert _repos(report_json()["no_enforcement"]) == _repos(ANSWER["no_enforcement"])


# A required check whose job exists but is skipped by an ``if:`` (echoform's
# "ci / DB migration check") still reports its name on GitHub, so listing it or
# not are both defensible; either is accepted (corrected 2026-10-01, after the
# first calibration cells; see the stage0-ext findings note).
OPTIONAL = {"echoform": {"ci / DB migration check"}}


def test_mismatched_contexts():
    got = _mapping(report_json()["mismatched_contexts"])
    want = _mapping(ANSWER["mismatched_contexts"])
    for repo, contexts in OPTIONAL.items():
        for mapping in (got, want):
            if repo in mapping:
                mapping[repo] = mapping[repo] - contexts
                if not mapping[repo]:
                    del mapping[repo]
    assert got == want


def test_strict_policy():
    assert _repos(report_json()["strict"]) == _repos(ANSWER["strict"])


def test_missing_properties():
    assert _mapping(report_json()["missing_properties"]) == _mapping(ANSWER["missing_properties"])


def test_counts():
    data = report_json()
    assert int(data["scanned"]) == ANSWER["scanned"]
    assert int(data["archived_skipped"]) == ANSWER["archived_skipped"]
