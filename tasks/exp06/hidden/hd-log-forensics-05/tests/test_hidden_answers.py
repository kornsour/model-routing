"""Hidden grader: runner log forensics (exp06 stratum D)."""

import json
from pathlib import Path

import pytest

KEY = {
    "sla_breaches": ["nightly-0903-02", "nightly-0904-02"],
    "failed_runs": ["nightly-0902-02", "nightly-0905-02"],
    "median_nightly_minutes": 155,
    "most_retried_job": {"job": "extract_orders", "retries": 3},
    "load_orders_attempt_minutes": 750,
    "runs_with_upstream_failures": 2,
    "first_warehouse_saturation": "2026-09-01T02:40:00Z",
}


@pytest.fixture(scope="module")
def answer():
    return json.loads((Path.cwd() / "ANSWER.json").read_text())


@pytest.mark.parametrize("key", sorted(KEY))
def test_answer(answer, key):
    got, want = answer[key], KEY[key]
    if isinstance(want, list):
        assert sorted(got) == want
    elif isinstance(want, dict):
        assert got["job"] == want["job"] and int(got["retries"]) == want["retries"]
    elif isinstance(want, int):
        assert float(got) == want
    else:
        assert got == want
