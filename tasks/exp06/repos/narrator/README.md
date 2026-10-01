# narrator

Turns an EPUB into a chaptered M4B audiobook with a local text-to-speech
engine. Personal project; runs on a laptop, no cloud services.

## Usage

```bash
python -m narrator book.epub --voice amber --out book.m4b
```

## Docs

- `docs/tts.md` — the TTS engine and how voices are configured.
- `docs/legacy-voices.md` — the legacy voice presets (still supported).
- `docs/chaptering.md` — how chapters and pauses are derived from the EPUB.
- `docs/ideas.md` — backlog.
