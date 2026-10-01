# gh snapshot

Every `gh api` response this sweep needs, saved by API path (the live API was
captured at the same moment; treat this as the source of truth).

| `gh api ...` | file |
|---|---|
| `/orgs/Copperline/repos` | `orgs/Copperline/repos.json` |
| `/users/ellisport/repos` | `users/ellisport/repos.json` |
| `/orgs/Copperline/rulesets` and `/orgs/Copperline/rulesets/{id}` | `orgs/Copperline/rulesets.json`, `orgs/Copperline/rulesets/{id}.json` |
| `/orgs/Copperline/properties/schema` | `orgs/Copperline/properties/schema.json` |
| `/orgs/Copperline/properties/values` | `orgs/Copperline/properties/values.json` (a property absent from a repo's list is unset) |
| `/repos/{owner}/{repo}/rulesets` and `.../rulesets/{id}` | `repos/{owner}/{repo}/rulesets.json`, `repos/{owner}/{repo}/rulesets/{id}.json` (repo-level rulesets only) |
| `/repos/{owner}/{repo}/branches/{default}/protection` | `repos/{owner}/{repo}/branches/main/protection.json` (a body with `"status": "404"` is the 404) |
| workflow files | `repos/{owner}/{repo}/contents/.github/workflows/*.yml`, listed in `index.json` |
| reusable workflows called as `Copperline/.github-private/...@sha` | `repos/Copperline/.github-private/contents/.github/workflows/` |

A personal account has no org rulesets, org variables or custom properties.
Workflows called from `ellisport/gh-automation` are under that repo's directory.
