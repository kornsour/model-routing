# ts-starter

A minimal TypeScript starter for new services and libraries. Click **Use this
template** on GitHub, then rename the package in `package.json`.

## What you get

- Strict `tsconfig.json` and type-stripped execution on Node 24 (no build step for tests).
- `node --test` for unit tests, colocated as `*.test.ts`.
- Biome for lint and format.
- A CI workflow that calls the shared reusable workflow.

## Layout

```
src/            library code and colocated tests
docs/           conventions for repos created from this template
.github/        CI caller stub
```

## Commands

```bash
npm test        # node --test
npm run check   # biome
```
