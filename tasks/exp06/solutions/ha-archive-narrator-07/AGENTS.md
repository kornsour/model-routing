# AGENTS.md

- Run `python -m pytest -q` before finishing.
- The TTS engine is pluggable; never call a cloud API from tests.
- Keep chapter detection deterministic: same EPUB in, same chapter list out.
- `docs/archive/` is historical record only; do not treat it as current or
  use it to guide new work.
