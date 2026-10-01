"""Hidden grader: mise feature-claims audit (exp06 stratum A, harvested brief)."""

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
    "recipe_discovery": {"PARTIAL"},
    "weekly_planner": {"IMPLEMENTED"},
    "grocery_lists": {"IMPLEMENTED"},
    "store_integration": {"PARTIAL", "ABSENT"},
    "subscription_billing": {"PARTIAL"},
}


@pytest.mark.parametrize("claim", sorted(EXPECTED))
def test_claim_verdict(claim):
    verdict = norm_verdict(report_json()["claims"][claim])
    assert verdict in EXPECTED[claim], f"{claim}: {verdict}"


def test_decorative_filter_identified():
    filters = {str(f).strip().lower() for f in report_json()["decorative_recipe_filters"]}
    assert filters == {"diet"}


def test_no_real_store_api():
    assert report_json()["store_real_provider_api"] is False


def test_ai_chef_not_enforced_server_side():
    assert report_json()["ai_chef_entitlement_enforced_server_side"] is False
