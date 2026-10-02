#!/usr/bin/env bash
# Builds .github-private's history for ha-branch-triage-02: 106 commits on main
# after the fixture's first commit, and seven branches whose ground truth is:
#   agent/portfolio-static-export-tracker  squash-merged as #88            -> DELETE
#   chore/issue-31-analyzer-blocker        #103 merged 3 of 7; 4 unique,   -> PR
#                                          no overlap with main
#   chore/issue-84-66-82-verification      inside integration squash #95   -> DELETE
#   docs/aws-domain-inventory-2026-08-14   edits a doc main archived; every
#                                          row is in docs/DOMAINS.md       -> DELETE (or NEEDS-DECISION)
#   docs/tailscale-key-expiry-reauth       reused after #99/#100; .gitignore
#                                          change already on main, two
#                                          unique docs commits, clean      -> PR
#   rescue/aws-denials                     table fully contained in
#                                          docs/AWS-ACCESS-DENIALS.md      -> DELETE (or NEEDS-DECISION)
#   work/runner-ops-51-53-70               #110 merged c1; c2 unique and
#                                          conflicts with main's rewrite   -> NEEDS-DECISION
set -euo pipefail
# The sandbox's first commit carries today's date; back-date it so the history
# below is never older than its own root (clock skew breaks `git rev-list A..B`).
GIT_COMMITTER_DATE="2026-07-01T09:00:00Z" git -c user.name=sandbox -c user.email=sandbox@local \
  commit -q --amend --no-edit --date="2026-07-01T09:00:00Z"
python3 - <<'PY'
import os
import subprocess
from pathlib import Path

ENV = dict(os.environ, GIT_AUTHOR_NAME="Org Bot", GIT_AUTHOR_EMAIL="bot@copperline.example",
           GIT_COMMITTER_NAME="Org Bot", GIT_COMMITTER_EMAIL="bot@copperline.example")
clock = [0]


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, env=ENV).stdout.strip()


def write(path, text, append=False):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if append:
        with p.open("a") as f:
            f.write(text)
    else:
        p.write_text(text)


def commit(message):
    clock[0] += 1
    day, hour = divmod(clock[0], 12)
    date = f"2026-08-{15 + day // 3:02d}T{8 + hour:02d}:{(day % 3) * 20:02d}:00Z"
    ENV["GIT_AUTHOR_DATE"] = ENV["GIT_COMMITTER_DATE"] = date
    git("add", "-A")
    git("commit", "-q", "-m", message)


DOMAIN_ROWS = [f"| svc{i}.copperline.example | Route 53 | Z1{i:02d} | service {i} |\n" for i in range(1, 20)]
DENIAL_ROWS = [
    "| 2026-08-20 | deploy-mise | s3:PutBucketPolicy | missing in boundary |\n",
    "| 2026-08-21 | deploy-binwise | ecr:BatchGetImage | repo policy |\n",
    "| 2026-08-22 | provision-domain | route53:ChangeResourceRecordSets | zone not tagged |\n",
]
main_n = [0]


def filler():
    main_n[0] += 1
    write("docs/CHANGELOG.md", f"- change {main_n[0]}: routine org config update\n", append=True)
    commit(f"chore: org config update {main_n[0]}")


def main_commit(message, fn):
    main_n[0] += 1
    fn()
    commit(message)


def on_main_until(n):
    while main_n[0] < n:
        filler()


git("branch", "-M", "main")

# docs/aws-domain-inventory-2026-08-14: forks at the first commit, 19 commits.
git("switch", "-q", "-c", "docs/aws-domain-inventory-2026-08-14")
for i, row in enumerate(DOMAIN_ROWS, start=1):
    write("docs/AWS-DOMAIN-INVENTORY.md", row, append=True)
    commit(f"docs(domains): add svc{i}.copperline.example")
git("switch", "-q", "main")

on_main_until(29)
git("switch", "-q", "-c", "rescue/aws-denials")
write("docs/AWS-DENIALS-2026-08.md", "# AWS access denials, rescued from a scratch session\n\n| date | role | action | cause |\n|---|---|---|---|\n" + "".join(DENIAL_ROWS))
commit("rescue: AWS denials observed during the August deploys")
git("switch", "-q", "main")

on_main_until(49)
def archive_domains():
    text = Path("docs/AWS-DOMAIN-INVENTORY.md").read_text()
    git("mv", "docs/AWS-DOMAIN-INVENTORY.md", "docs/archive/AWS-DOMAIN-INVENTORY-2026-08.md")
    write("docs/DOMAINS.md", "# Domains (current)\n\nSuperset of the August inventory, kept current.\n\n| domain | registrar | hosted zone | used by |\n|---|---|---|---|\n| copperline.example | Route 53 | Z01 | marketing site |\n| mise.example | Route 53 | Z02 | mise |\n" + "".join(DOMAIN_ROWS) + "| folio.example | Cloudflare | - | personal site |\n")
main_commit("docs: archive the August domain inventory, add docs/DOMAINS.md (#64)", archive_domains)

on_main_until(54)
main_commit("docs: AWS access denials log (#71)", lambda: write("docs/AWS-ACCESS-DENIALS.md", "# AWS access denials\n\nEvery denial seen in CloudTrail since August, with the fix.\n\n| date | role | action | cause |\n|---|---|---|---|\n" + "".join(DENIAL_ROWS) + "| 2026-09-02 | deploy-cohort | kms:Decrypt | key policy |\n"))

on_main_until(59)
TRACKER = "# Portfolio static export tracker\n\n- [x] export folio-site as static HTML\n- [ ] move hosting decision to issue #7\n"
git("switch", "-q", "-c", "agent/portfolio-static-export-tracker")
write("docs/PORTFOLIO-EXPORT.md", TRACKER)
commit("docs: portfolio static-export tracker")
git("switch", "-q", "main")
main_commit("docs: portfolio static-export tracker (#88)", lambda: write("docs/PORTFOLIO-EXPORT.md", TRACKER))

on_main_until(75)
VERIFY_LINE = "# Verified closures: #84 #66 #82 (all referenced in docs/CHANGELOG.md).\n"
git("switch", "-q", "-c", "chore/issue-84-66-82-verification")
write("tools/verify-issues.sh", VERIFY_LINE, append=True)
commit("chore: verify #84 #66 #82 closure")
git("switch", "-q", "main")
def integration():
    write("tools/verify-issues.sh", VERIFY_LINE, append=True)
    write("docs/CHANGELOG.md", "- hygiene batch: verify-issues closures, typo fixes\n", append=True)
main_n[0] += 1
integration()
ENV_MSG = "chore: batch of hygiene fixes (#95)\n\n* chore: verify #84 #66 #82 closure\n* docs: typo fixes in CHANGELOG\n"
commit(ENV_MSG)

on_main_until(84)
main_commit("docs: tailscale re-auth notes (#99)", lambda: write("docs/TAILSCALE.md", "# Tailscale\n\nHow fleet hosts join the tailnet.\n"))
on_main_until(87)
main_commit("docs: tailscale ACL note (#100)", lambda: write("docs/TAILSCALE.md", "ACLs: runners may reach only the egress proxy.\n", append=True))
on_main_until(94)
git("switch", "-q", "-c", "work/runner-ops-51-53-70")
write("docs/RUNNER-OPS.md", "# Runner operations\n\nCovers #51 (listing) and #53 (labels).\n")
commit("docs: runner ops for #51 #53")
write("tools/runner-ops.sh", "#!/usr/bin/env bash\n# Runner fleet operations: list runners, drain one before host maintenance (#70).\nset -euo pipefail\ncase \"${1:-list}\" in\n  list) echo \"runner-1 online\"; echo \"runner-2 online\" ;;\n  drain) echo \"draining ${2:?runner name}\"; touch \"/tmp/drain-${2}\" ;;\n  *) echo \"usage: runner-ops.sh list|drain <runner>\" >&2; exit 2 ;;\nesac\n")
commit("tools: drain a runner before maintenance (#70)")
git("switch", "-q", "main")
main_commit("docs: runner ops for #51 #53 (#110)", lambda: write("docs/RUNNER-OPS.md", "# Runner operations\n\nCovers #51 (listing) and #53 (labels).\n"))
on_main_until(98)
main_commit("refactor(tools): runner-ops reads the fleet from runners.json (#114)", lambda: write("tools/runner-ops.sh", "#!/usr/bin/env bash\n# Runner fleet operations, driven by tools/runners.json.\nset -euo pipefail\nfleet=\"$(dirname \"$0\")/runners.json\"\ncase \"${1:-list}\" in\n  list) python3 -c 'import json,sys; [print(r[\"name\"], r[\"state\"]) for r in json.load(open(sys.argv[1]))]' \"$fleet\" ;;\n  *) echo \"usage: runner-ops.sh list\" >&2; exit 2 ;;\nesac\n") or write("tools/runners.json", '[{"name": "runner-1", "state": "online"}, {"name": "runner-2", "state": "online"}]\n'))

on_main_until(101)
git("switch", "-q", "-c", "chore/issue-31-analyzer-blocker")
for i in range(1, 4):
    write("tools/workflow-analyzer/README.md", f"Step {i}: composite-action resolution.\n", append=True)
    commit(f"feat(analyzer): composite action resolution, part {i}")
merged_readme = Path("tools/workflow-analyzer/README.md").read_text()
for i in range(1, 5):
    lines = [f"check_{i}_{j}() {{ grep -q 'uses: ./{j}' \"$1\" && echo 'composite {j}'; }}\n" for j in range(137)]
    write(f"tools/workflow-analyzer/checks-{i}.sh", "#!/usr/bin/env bash\n# Composite-action checks, batch %d (#31).\n" % i + "".join(lines))
    commit(f"feat(analyzer): check batch {i} for composite actions (#31)")
git("switch", "-q", "main")
main_commit("feat(analyzer): composite action resolution (#103)", lambda: write("tools/workflow-analyzer/README.md", merged_readme))

git("switch", "-q", "-c", "docs/tailscale-key-expiry-reauth")
write(".gitignore", ".env\n.DS_Store\n", append=True)
commit("chore: ignore .env and .DS_Store")
write("docs/TAILSCALE-REAUTH.md", "# Re-authenticating expired Tailscale node keys\n\n1. `tailscale status` shows `expired`.\n2. Re-auth with a one-off key from the admin console (#47).\n")
commit("docs: re-auth runbook for expired node keys (#47)")
write("docs/TAILSCALE-REAUTH.md", "3. Disable key expiry only for tagged infrastructure nodes.\n", append=True)
commit("docs: key-expiry policy for tagged nodes")
git("switch", "-q", "main")
on_main_until(103)
main_commit("chore: gitignore hygiene (#107)", lambda: write(".gitignore", ".env\n.DS_Store\n", append=True))
on_main_until(106)
PY
origin="$(pwd)/.git/fixture-origin.git"
git clone -q --bare . "$origin"
git remote add origin "$origin"
git fetch -q origin
git switch -q main
# The listed branches are local-only ("no upstream") except where the brief says
# they track; remove the remote copies of the local-only ones.
for b in agent/portfolio-static-export-tracker rescue/aws-denials work/runner-ops-51-53-70; do
  git push -q origin --delete "$b"
done
git fetch -q --prune origin
