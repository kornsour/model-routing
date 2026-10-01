"""Hidden grader wrapper (exp06 stratum A): Go hidden tests, gofmt, vet, Python client tests."""

import subprocess
from pathlib import Path

ROOT = Path.cwd()


def _run(*cmd):
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600)
    return proc.returncode, proc.stdout + proc.stderr


def test_go_suite_including_hidden_tests():
    code, out = _run("go", "test", "-count=1", "./...")
    assert code == 0, out[-4000:]


def test_gofmt_and_vet_clean():
    code, out = _run("gofmt", "-l", ".")
    assert code == 0 and not out.strip(), f"gofmt: {out}"
    code, out = _run("go", "vet", "./...")
    assert code == 0, out[-3000:]


def test_python_client_tests():
    code, out = _run("python3", "-m", "unittest", "discover", "-s", "python/tests")
    assert code == 0, out[-3000:]


def test_no_year_one_timestamps_documented():
    for path in [ROOT / "README.md", ROOT / "docs/openapi.yaml", *sorted((ROOT / "python").rglob("*.py"))]:
        assert "0001-01-01" not in path.read_text(), f"{path.relative_to(ROOT)} still documents the year-1 ended_at"
