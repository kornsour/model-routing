"""Hidden grader: simulated nightly investigation (exp06 stratum D)."""

import json
from pathlib import Path

import pytest

KEY = {
    "extract_orders_first_start": 8,
    "extract_inventory_attempts": 3,
    "extract_inventory_retry_times": [8, 17],
    "upstream_failed_jobs": ["customer_report", "notify"],
    "notify_reason": "upstream customer_report upstream_failed",
    "makespan": 53,
    "load_inventory_ready_at": 23,
    "load_inventory_wait": 17,
    "makespan_with_4_warehouse": 44,
}


@pytest.fixture(scope="module")
def answer():
    return json.loads((Path.cwd() / "ANSWER.json").read_text())


@pytest.mark.parametrize("key", sorted(KEY))
def test_answer(answer, key):
    got = answer[key]
    want = KEY[key]
    if isinstance(want, list) and want and isinstance(want[0], (int, float)):
        assert [float(x) for x in got] == [float(x) for x in want]
    elif isinstance(want, (int, float)):
        assert float(got) == float(want)
    else:
        assert got == want
