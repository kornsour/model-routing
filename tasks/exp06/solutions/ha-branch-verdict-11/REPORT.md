# packlight `feat/aws-staging`

VERDICT: DELETE

- Squash check: `git cherry main <synth>` gives `+` (content not upstream), so it was never merged.
- Files absent from main, all infra scaffolding: `sst.config.ts`, `sst-env.d.ts`, `.github/workflows/aws-staging.yml`. No application code.
- Behind main by 11; `git diff --shortstat main..feat/aws-staging`: 13 files changed, 25 insertions(+), 50 deletions(-).
- Superseded: main deploys with `scripts/deploy-aws.sh` from `.github/workflows/deploy.yml`, and `docs/deploy.md` records that SST was evaluated and dropped.
- Open issue: #41 "Staging environment on AWS" (already served by main's staging deploy). No PR for the branch.

The branch is one commit of regenerable SST scaffolding, the approach was dropped on main in favour of a script, and nothing unique would be lost.

```json
{"verdict": "DELETE", "absent_from_main": {"infra": ["sst.config.ts", "sst-env.d.ts", ".github/workflows/aws-staging.yml"], "application": []}, "behind": 11}
```
