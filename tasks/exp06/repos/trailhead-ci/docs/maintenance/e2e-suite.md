# The e2e suite

Local-only (ADR-0023). `scripts/hooks/pre-push` runs it before every push that
touches `src/`, `e2e/` or `drizzle/`, and skips with a notice when Playwright
browsers or `DATABASE_URL` are missing. `SKIP_E2E=1` skips it for one push.
