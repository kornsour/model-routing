# birchwood

Birchwood is the booking calendar behind the Copperline studio sites: it
holds rooms, slots and holds, and exposes a small JSON API the sites call.

## Quick start

```bash
python -m pytest -q
python -m birchwood serve --port 8086
```

## Documentation

- `docs/architecture.md` — how requests flow from the site widget to the database.
- `docs/deploy.md` — how a release reaches production.
- `docs/adr/` — architecture decision records.
- `docs/roadmap-2026-h1.md` — what we are building this half.

## Licence

Proprietary. Copyright Copperline.
