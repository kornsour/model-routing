"""Hidden grader: services.ini resolution (exp06 stratum D)."""

import json
from pathlib import Path

import pytest

KEY = {
    "api_canary_url": "http://api-canary.internal:9090/",
    "api_canary_port": "9090",
    "api_canary_log_level": "debug",
    "api_banner": "Welcome; please log in",
    "api_motd": "Maintenance window",
    "worker_queue": "api-jobs",
    "worker_url": "http://base.internal:8080/work",
    "worker_timeout": "${seconds}",
    "api_canary_key_count": 10,
    "failing_keys": ["billing:endpoint", "ledger:url"],
}


@pytest.fixture(scope="module")
def answer():
    return json.loads((Path.cwd() / "ANSWER.json").read_text())


@pytest.mark.parametrize("key", sorted(KEY))
def test_answer(answer, key):
    got = answer[key]
    if key == "failing_keys":
        got = sorted(got)
    if key == "api_canary_key_count":
        got = int(got)
    assert got == KEY[key]
