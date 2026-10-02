"""Hidden grader: local CI-equivalent `pnpm verify` (exp06 stratum A, harvested brief).

Runs the repo's own `pnpm verify` command against stub tools in a scratch copy
of the sandbox, so each CI check can be made to pass or fail on demand.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path.cwd()
PRE_PUSH_HEADER = json.loads('''["# pre-push: runs the e2e suite before anything leaves this machine.", "#", "# Design (deliberate; keep it):", "# - If the test environment is absent (no Playwright browsers, no local", "#   database), SKIP with a loud notice and exit 0. Only an actual failure", "#   blocks. A gate you must disable to do your job is a gate you stop reading.", "# - Is this push worth 70 seconds? If nothing under src/, e2e/ or drizzle/", "#   changed, skip the suite with a notice.", "# - SKIP_E2E=1 is the documented escape hatch for an emergency push.", "set -euo pipefail", ""]''')

PNPM = r'''#!/usr/bin/env bash
echo "pnpm $*" >> "$STUB_LOG"
args=("$@")
[[ "${args[0]:-}" == "run" ]] && args=("${args[@]:1}")
key="${args[*]:-}"
case "$key" in
  check|"check "*|"exec biome"*) exit "${FAIL_CHECK:-0}" ;;
  *tsc*|typecheck*) exit "${FAIL_TSC:-0}" ;;
  test|"test "*|"exec vitest"*) exit "${FAIL_TEST:-0}" ;;
  build|"build "*|"exec next build"*) exit "${FAIL_BUILD:-0}" ;;
  install*) exit 0 ;;
  *) exit 0 ;;
esac
'''
NPX = r'''#!/usr/bin/env bash
echo "npx $*" >> "$STUB_LOG"
case "$*" in *tsc*) exit "${FAIL_TSC:-0}" ;; *biome*) exit "${FAIL_CHECK:-0}" ;; *) exit 0 ;; esac
'''
SEMGREP = r'''#!/usr/bin/env bash
echo "semgrep $*" >> "$STUB_LOG"
exit "${FAIL_SEMGREP:-0}"
'''
LOCKFILE = r'''#!/usr/bin/env bash
echo "check-lockfile.sh ran" >> "$STUB_LOG"
exit "${FAIL_LOCKFILE:-0}"
'''
MIGSEQ = '''import { appendFileSync } from "node:fs";
appendFileSync(process.env.STUB_LOG, "check-migration-sequence ran\\n");
process.exit(Number(process.env.FAIL_MIGSEQ ?? 0));
'''


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("verify")
    repo = tmp / "repo"
    shutil.copytree(ROOT, repo, symlinks=True, ignore=shutil.ignore_patterns("node_modules"))
    (repo / "scripts/check-lockfile.sh").write_text(LOCKFILE)
    (repo / "scripts/check-lockfile.sh").chmod(0o755)
    (repo / "scripts/check-migration-sequence.mjs").write_text(MIGSEQ)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "graded state")
    bare = tmp / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(["git", "remote", "remove", "origin"], cwd=repo, capture_output=True)
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
    _git(repo, "fetch", "-q", "origin")
    _git(repo, "branch", "--set-upstream-to=origin/main")
    stubs = tmp / "bin"
    stubs.mkdir()
    for name, body in (("pnpm", PNPM), ("npx", NPX)):
        (stubs / name).write_text(body)
        (stubs / name).chmod(0o755)
    with_semgrep = tmp / "bin-semgrep"
    with_semgrep.mkdir()
    (with_semgrep / "semgrep").write_text(SEMGREP)
    (with_semgrep / "semgrep").chmod(0o755)
    return {"repo": repo, "tmp": tmp, "stubs": stubs, "semgrep": with_semgrep}


def run_verify(ws, semgrep=False, **fail):
    scripts = json.loads((ws["repo"] / "package.json").read_text()).get("scripts", {})
    assert "verify" in scripts, "package.json has no verify script"
    log = ws["tmp"] / "stub.log"
    log.write_text("")
    node_dir = str(Path(shutil.which("node")).parent)
    path = [str(ws["stubs"])] + ([str(ws["semgrep"])] if semgrep else []) + [node_dir, "/usr/bin", "/bin"]
    env = {k: v for k, v in os.environ.items() if not k.startswith("FAIL_")}
    env.update({"PATH": ":".join(path), "STUB_LOG": str(log), "CI": "", **{k: str(v) for k, v in fail.items()}})
    proc = subprocess.run(["bash", "-c", scripts["verify"]], cwd=ws["repo"], env=env, capture_output=True, text=True, timeout=600)
    return proc.returncode, proc.stdout + proc.stderr, log.read_text()


def test_all_green_runs_every_check_and_admits_semgrep_skip(workspace):
    code, out, log = run_verify(workspace)
    assert code == 0, out[-3000:]
    norm = log.replace("pnpm run ", "pnpm ")
    ran = {
        "biome": "pnpm check" in norm or "biome" in norm,
        "tsc": "tsc --noEmit" in norm,
        "tests": "pnpm test" in norm or "vitest" in norm,
        "build": "pnpm build" in norm or "next build" in norm,
    }
    assert all(ran.values()), f"checks that never ran: {[k for k, v in ran.items() if not v]}\n{log}"
    assert "check-lockfile.sh ran" in log, "lockfile check never ran"
    assert "check-migration-sequence ran" in log, "migration-sequence check never ran"
    lower = out.lower()
    assert "semgrep" in lower and "skip" in lower, "semgrep absence is not reported as a skip"


def test_semgrep_runs_when_present(workspace):
    code, out, log = run_verify(workspace, semgrep=True)
    assert code == 0, out[-3000:]
    assert "semgrep " in log, "semgrep was on PATH but never ran"


@pytest.mark.parametrize(
    ("fail", "command"),
    [("FAIL_TSC", "tsc --noEmit"), ("FAIL_LOCKFILE", "check-lockfile"), ("FAIL_BUILD", "build"), ("FAIL_MIGSEQ", "check-migration-sequence")],
)
def test_a_failure_is_named_with_its_command(workspace, fail, command):
    code, out, _ = run_verify(workspace, **{fail: 1})
    assert code != 0, f"{fail}: verify passed"
    assert command in out, f"{fail}: output does not name the reproduce command {command!r}"


def test_schema_change_without_migration_fails(workspace):
    repo = workspace["repo"]
    schema = repo / "src/db/schema.ts"
    schema.write_text(schema.read_text() + "\n// graded change\n")
    _git(repo, "commit", "-qam", "schema change")
    code, out, _ = run_verify(workspace)
    assert code != 0, "schema.ts changed with no migration, yet verify passed"
    (repo / "drizzle/0002_graded.sql").write_text("ALTER TABLE role ADD COLUMN graded text;\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "migration")
    code, out, _ = run_verify(workspace)
    assert code == 0, out[-3000:]


def test_pre_push_keeps_its_design_and_calls_verify():
    text = (ROOT / "scripts/hooks/pre-push").read_text()
    missing = [line for line in PRE_PUSH_HEADER if line.strip() and line not in text]
    assert not missing, f"pre-push header changed: {missing[:2]}"
    assert "SKIP_E2E" in text and "verify" in text


def test_docs_describe_pnpm_verify():
    assert "pnpm verify" in (ROOT / "CLAUDE.md").read_text()
    docs = [p.read_text() for p in (ROOT / "docs").rglob("*.md")]
    assert any("pnpm verify" in d and "semgrep" in d.lower() for d in docs), "no runbook covers pnpm verify and semgrep"
