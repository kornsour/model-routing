# Rulesets and branch protection sweep

Scanned 45 repos (22 Copperline including `.github-private`, 23 ellisport); skipped 3 archived.

## Answers

**No enforcement:** Copperline/northstar-docs, ellisport/gh-automation, ellisport/dotfiles, ellisport/chess-clock, ellisport/tidy-photos, ellisport/md-slides, ellisport/budget-cli, ellisport/weather-pi, ellisport/habit-log, ellisport/recipe-scale, ellisport/snippets, ellisport/lab-notes, ellisport/cron-pal, ellisport/zine, ellisport/kata, ellisport/pixel-font

**Required contexts that no job produces:**
- Copperline/echoform: `ci / DB migration check`
- Copperline/ledgerline: `ci / DB migration check`
- Copperline/routewise: `ci / Lint (ruff)`, `ci / Tests (pytest)`
- Copperline/tallyhub: `lockfile / integrity`
- Copperline/quillstack: `ci / Build`, `ci / Lint & format (Biome)`, `ci / Type check`, `ci / Unit tests (Vitest)`
- ellisport/folio-site: `deploy`
- ellisport/design-kit: `visual-regression`

**strict_required_status_checks_policy on:** Copperline/beacon, Copperline/relay-bot, ellisport/folio-site, ellisport/trackbook, ellisport/narrator, ellisport/ts-starter, ellisport/design-kit

**Missing targeting properties:**
- Copperline/northstar-docs: tier
- Copperline/pantry-api: tier
- Copperline/swatch: database
- Copperline/harbor-sim: ci-managed

```json
{
 "no_enforcement": [
  "Copperline/northstar-docs",
  "ellisport/gh-automation",
  "ellisport/dotfiles",
  "ellisport/chess-clock",
  "ellisport/tidy-photos",
  "ellisport/md-slides",
  "ellisport/budget-cli",
  "ellisport/weather-pi",
  "ellisport/habit-log",
  "ellisport/recipe-scale",
  "ellisport/snippets",
  "ellisport/lab-notes",
  "ellisport/cron-pal",
  "ellisport/zine",
  "ellisport/kata",
  "ellisport/pixel-font"
 ],
 "mismatched_contexts": {
  "Copperline/echoform": [
   "ci / DB migration check"
  ],
  "Copperline/ledgerline": [
   "ci / DB migration check"
  ],
  "Copperline/routewise": [
   "ci / Lint (ruff)",
   "ci / Tests (pytest)"
  ],
  "Copperline/tallyhub": [
   "lockfile / integrity"
  ],
  "Copperline/quillstack": [
   "ci / Build",
   "ci / Lint & format (Biome)",
   "ci / Type check",
   "ci / Unit tests (Vitest)"
  ],
  "ellisport/folio-site": [
   "deploy"
  ],
  "ellisport/design-kit": [
   "visual-regression"
  ]
 },
 "strict": [
  "Copperline/beacon",
  "Copperline/relay-bot",
  "ellisport/folio-site",
  "ellisport/trackbook",
  "ellisport/narrator",
  "ellisport/ts-starter",
  "ellisport/design-kit"
 ],
 "missing_properties": {
  "Copperline/northstar-docs": [
   "tier"
  ],
  "Copperline/pantry-api": [
   "tier"
  ],
  "Copperline/swatch": [
   "database"
  ],
  "Copperline/harbor-sim": [
   "ci-managed"
  ]
 },
 "archived_skipped": 3,
 "scanned": 45
}
```
