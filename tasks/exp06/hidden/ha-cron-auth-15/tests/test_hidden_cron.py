"""Hidden grader wrapper: runs the node:test suite that checks every cron route fails closed."""

import subprocess
from pathlib import Path


def test_cron_routes_fail_closed():
    proc = subprocess.run(
        ["node", "--test", "tests/hidden/cron-fail-closed.test.ts"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
