# pnpm verify

`pnpm verify` (`scripts/verify.sh`) runs every check CI runs: Biome, `tsc --noEmit`,
Vitest, the build, the DB migration check, Semgrep, the migration sequence and the
lockfile guard. The fast checks run in parallel; the build runs last. A red line
in the summary names the check and the command that reproduces it alone.

Semgrep is skipped, loudly, when it is not installed. For full parity install the
version CI pins: `pipx install semgrep==1.172.0`.

`scripts/hooks/pre-push` runs `pnpm verify` before the e2e suite. In an emergency,
`git push --no-verify` bypasses both; CI on `main` still runs as a backstop.
