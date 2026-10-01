#!/usr/bin/env bash
# Builds six nested clones for ha-branch-triage-08. Ground truth:
#   trackbook:examples-and-diff-verdict-fix  all 3 commits inside integration
#                                            squash #18 (bullets in its body) -> DELETE
#   trackbook:python-client-contract         6 unique commits, clean, issue #12 -> PR
#   crossfade:feat/m6-eval                   7 unique commits; main moved eval/
#                                            to evals/ and rewrote run.py      -> NEEDS-DECISION
#   packlight:fix/nanoid-3-3-18              main already has nanoid 3.3.19    -> DELETE
#   ml-notes:learn                           6 scratch commits, 2026-07-19     -> LEAVE-ALONE (or DELETE/NEEDS-DECISION)
#   mise origin/upstream/main                remote "upstream" fetches into
#                                            refs/remotes/origin/upstream/*;
#                                            commit is in main: prune + fix config
#   binwise origin/canonical/main            leftover of a removed remote; no
#                                            config creates it; commit in main: prune only
set -euo pipefail
# The outer directory is just a holder for the clones: drop them from its own
# index and ignore them, so only the nested repositories track their files.
git rm -r -q --cached Copperline ellisport
mkdir -p .git/info && printf 'Copperline/\nellisport/\n' >> .git/info/exclude
GIT_COMMITTER_DATE="2026-07-01T09:00:00Z" git -c user.name=sandbox -c user.email=sandbox@local \
  commit -q --amend --no-edit --date="2026-07-01T09:00:00Z"
python3 - <<'PY'
import os
import subprocess
from pathlib import Path

BASE = Path.cwd()
ENV = dict(os.environ, GIT_AUTHOR_NAME="Dev", GIT_AUTHOR_EMAIL="dev@example.com",
           GIT_COMMITTER_NAME="Dev", GIT_COMMITTER_EMAIL="dev@example.com")
clock = {"t": 0}


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=BASE / repo, check=True, capture_output=True, text=True, env=ENV).stdout.strip()


def write(repo, path, text, append=False):
    p = BASE / repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    if append:
        with p.open("a") as f:
            f.write(text)
    else:
        p.write_text(text)


def commit(repo, message, date=None):
    clock["t"] += 1
    if date is None:
        day, minute = divmod(clock["t"], 40)
        date = f"2026-08-{1 + day:02d}T10:{minute:02d}:00Z"
    ENV["GIT_AUTHOR_DATE"] = ENV["GIT_COMMITTER_DATE"] = date
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def init(repo):
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "initial commit", date="2026-07-02T09:00:00Z")


def publish(repo, local_only=()):
    origin = BASE / repo / ".git" / "fixture-origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(BASE / repo), str(origin)], check=True, env=ENV)
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "fetch", "-q", "origin")
    for b in local_only:
        git(repo, "push", "-q", "origin", "--delete", b)
    git(repo, "fetch", "-q", "--prune", "origin")
    git(repo, "branch", "-q", "--set-upstream-to=origin/main", "main")
    git(repo, "switch", "-q", "main")


def fillers(repo, n, path="CHANGELOG.md"):
    for i in range(n):
        write(repo, path, f"- maintenance {clock['t']}\n", append=True)
        commit(repo, f"chore: maintenance {clock['t']}")


# ---------------------------------------------------------------- trackbook
R = "ellisport/trackbook"
init(R)
fillers(R, 4)
git(R, "switch", "-q", "-c", "examples-and-diff-verdict-fix")
EX = {"examples/basic.json": '{"run": "a", "metrics": {"loss": 0.31}}\n',
      "examples/diff.json": '{"left": "a", "right": "b", "verdict": "changed"}\n'}
write(R, "examples/basic.json", EX["examples/basic.json"]); commit(R, "examples: basic run")
write(R, "examples/diff.json", EX["examples/diff.json"]); commit(R, "examples: diff of two runs")
VERDICT = 'package diff\n\n// Verdict summarises how two runs differ.\nfunc Verdict(changed int) string {\n\tswitch {\n\tcase changed == 0:\n\t\treturn "same"\n\tcase changed < 0:\n\t\treturn "invalid"\n\tdefault:\n\t\treturn "changed"\n\t}\n}\n'
write(R, "internal/diff/verdict.go", VERDICT); commit(R, "fix(diff): negative change counts are invalid, not changed")
git(R, "switch", "-q", "main")
fillers(R, 2)
for path, text in EX.items():
    write(R, path, text)
write(R, "internal/diff/verdict.go", VERDICT)
write(R, "docs/examples.md", "# Examples\n\nSee `examples/` for one file per verdict.\n")
commit(R, "feat: examples, diff verdicts and docs (#18)\n\n* examples: basic run\n* examples: diff of two runs\n* fix(diff): negative change counts are invalid, not changed\n* docs: examples page\n")
fillers(R, 3)
git(R, "switch", "-q", "-c", "python-client-contract")
for i in range(1, 7):
    write(R, f"python/tests/test_contract_{i}.py", f'"""Contract test {i}: the client and server agree on field {i}."""\n\n\ndef test_field_{i}():\n    assert True\n')
    commit(R, f"test(python): client contract, field {i}")
git(R, "switch", "-q", "main")
fillers(R, 2)
publish(R, local_only=("examples-and-diff-verdict-fix", "python-client-contract"))

# ---------------------------------------------------------------- crossfade
R = "Copperline/crossfade"
init(R)
fillers(R, 2)
git(R, "switch", "-q", "-c", "feat/m6-eval")
for i in range(1, 8):
    write(R, "eval/run.py", f"\ndef m6_case_{i}():\n    return 'beat-match within {i * 5} ms'\n", append=True)
    commit(R, f"eval(m6): case {i}", date=f"2026-08-2{min(i, 8)}T09:00:00Z")
git(R, "switch", "-q", "main")
git(R, "mv", "eval", "evals")
write(R, "evals/run.py", '"""Milestone evals, table-driven (replaces the per-case functions)."""\n\nCASES = {"m5": "pass"}\n\n\ndef run():\n    return dict(CASES)\n')
commit(R, "refactor(evals): table-driven harness under evals/ (#31)")
fillers(R, 6)
publish(R, local_only=("feat/m6-eval",))

# ---------------------------------------------------------------- packlight
R = "Copperline/packlight"
init(R)
fillers(R, 2)
git(R, "switch", "-q", "-c", "fix/nanoid-3-3-18")
write(R, "package.json", (BASE / R / "package.json").read_text().replace('"3.3.17"', '"3.3.18"'))
write(R, "pnpm-lock.yaml", "# lockfile excerpt\nnanoid@3.3.18:\n  resolution: {integrity: sha512-mid}\n")
commit(R, "fix(deps): bump nanoid to 3.3.18 (security)")
git(R, "switch", "-q", "main")
write(R, "package.json", (BASE / R / "package.json").read_text().replace('"3.3.17"', '"3.3.19"'))
write(R, "pnpm-lock.yaml", "# lockfile excerpt\nnanoid@3.3.19:\n  resolution: {integrity: sha512-new}\n")
commit(R, "build(deps): bump nanoid from 3.3.17 to 3.3.19 (#58)")
fillers(R, 3)
publish(R, local_only=("fix/nanoid-3-3-18",))

# ---------------------------------------------------------------- ml-notes
R = "Copperline/ml-notes"
init(R)
git(R, "switch", "-q", "-c", "learn")
for i in range(1, 7):
    write(R, "scratch/attention.md", f"- wip {i}: trying attention from scratch, numbers don't match yet\n", append=True)
    commit(R, f"wip {i}", date=f"2026-07-{12 + i:02d}T21:00:00Z")
git(R, "switch", "-q", "main")
fillers(R, 5, path="notes/index.md")
publish(R, local_only=("learn",))

# ---------------------------------------------------------------- mise: stale origin/upstream/main
R = "Copperline/mise"
template = BASE / R / ".git" / "fixture-template.git"
init(R)
subprocess.run(["git", "clone", "-q", "--bare", str(BASE / R), str(template)], check=True, env=ENV)
fillers(R, 4)
publish(R)
git(R, "remote", "add", "upstream", str(template))
git(R, "config", "--replace-all", "remote.upstream.fetch", "+refs/heads/*:refs/remotes/origin/upstream/*")
git(R, "fetch", "-q", "upstream")

# ---------------------------------------------------------------- binwise: stale origin/canonical/main
R = "Copperline/binwise"
init(R)
fillers(R, 2)
canonical = git(R, "rev-parse", "HEAD")
fillers(R, 3)
publish(R)
git(R, "update-ref", "refs/remotes/origin/canonical/main", canonical)
PY
