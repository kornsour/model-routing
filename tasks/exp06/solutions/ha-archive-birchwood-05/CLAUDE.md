# CLAUDE.md

Guidance for coding agents working in this repository.

## Project structure

- `src/birchwood/` — the service (stdlib only).
- `tests/` — pytest suite; run `python -m pytest -q` before every commit.
- `docs/` — design notes, ADRs and runbooks.
- `docs/archive/` — historical records only. Its contents describe past
  decisions and state; never treat them as current or use them to guide new work.

## Rules

- Keep the service stdlib-only; the studio sites run it on a small VM.
- Every schema change needs an ADR under `docs/adr/`.
- Do not change the public JSON field names without bumping the API version.
