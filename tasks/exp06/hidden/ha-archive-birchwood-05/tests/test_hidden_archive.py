"""Hidden grader: archive convention (exp06 stratum A, harvested brief)."""

import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
SPEC = json.loads('{"archive": "docs/archive", "wrong_archive": "archive", "moved": {"docs/adr/0001-use-sqlite.md": "0bf9db38c1d048d83c75470df4c54d292ef22d0541701e76ae4af6c5f5b7e95e", "docs/migration-sqlite-to-postgres.md": "2627f771d8c8dde2d4fb43e771cbed7cfbf575467642b708a51fd2e89b3c51c1", "docs/release-plan-v1.md": "3264f6e20dc0ffebcc4854f5b2e2e731a787d511481703f512026729c86657c6"}, "kept": {"docs/roadmap-2026-h1.md": "10f040a2e62406568a87b64ebecd419423f9b5e5b98b502dfb2cf54eed412294", "docs/adr/0002-holds-expire.md": "239d3819e76532a8a8961d10b6438981392e50423a28008a76f504ccd8d7eee1", "docs/adr/0003-json-api-versioning.md": "063d646b1c209205844c65406213afd6ee551a913765de998a12803cfdf49049", "docs/adr/0004-move-to-postgres.md": "89ecbb1d3bafda607ad48a282b0daefc65c5dcfa90b4ad86b1abb32aef546b63", "docs/architecture.md": "007a5914c65d9bd112ccc3a9aee110e943fd49292dc6e0d1f7eb3fe23e7ebe99", "docs/deploy.md": "6408f40bafebdcde4b11b39ec1076aedf6ae2b39e4ae517aefda2bdaca8ff95d", "docs/release-plan-v2.md": "78b1ce1313739eddf9a1c942eed3abe996ffb2228c9864774d04a44f61ff3edd"}, "noted": {"README.md": ["# birchwood", "", "Birchwood is the booking calendar behind the Copperline studio sites: it", "holds rooms, slots and holds, and exposes a small JSON API the sites call.", "", "## Quick start", "", "```bash", "python -m pytest -q", "python -m birchwood serve --port 8086", "```", "", "## Documentation", "", "- `docs/architecture.md` \\u2014 how requests flow from the site widget to the database.", "- `docs/deploy.md` \\u2014 how a release reaches production.", "- `docs/adr/` \\u2014 architecture decision records.", "- `docs/roadmap-2026-h1.md` \\u2014 what we are building this half.", "", "## Licence", "", "Proprietary. Copyright Copperline."], "CLAUDE.md": ["# CLAUDE.md", "", "Guidance for coding agents working in this repository.", "", "## Project structure", "", "- `src/birchwood/` \\u2014 the service (stdlib only).", "- `tests/` \\u2014 pytest suite; run `python -m pytest -q` before every commit.", "- `docs/` \\u2014 design notes, ADRs and runbooks.", "", "## Rules", "", "- Keep the service stdlib-only; the studio sites run it on a small VM.", "- Every schema change needs an ADR under `docs/adr/`.", "- Do not change the public JSON field names without bumping the API version."]}, "absent": ["AGENTS.md"]}')


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_archive_readme_states_purpose():
    readme = ROOT / SPEC["archive"] / "README.md"
    assert readme.is_file(), f"missing {readme}"
    text = readme.read_text().lower()
    assert "histor" in text and "current" in text


def test_archive_in_the_right_place():
    assert not (ROOT / SPEC["wrong_archive"]).exists(), "archive created in the wrong location"


def test_historical_files_moved_unchanged():
    archived = {_sha(p): p for p in (ROOT / SPEC["archive"]).rglob("*") if p.is_file()}
    for original, digest in SPEC["moved"].items():
        assert not (ROOT / original).exists(), f"{original} should have been archived"
        assert digest in archived, f"{original} is not in the archive byte-for-byte"


def test_current_files_left_alone():
    for path, digest in SPEC["kept"].items():
        assert (ROOT / path).is_file(), f"{path} was moved or deleted but is not clearly historical"
        assert _sha(ROOT / path) == digest, f"{path} was edited"


def test_root_docs_point_at_archive_with_minimal_edit():
    for path, lines in SPEC["noted"].items():
        text = (ROOT / path).read_text()
        assert SPEC["archive"] in text, (
            f"{path} has no note pointing at {SPEC['archive']}/"
        )
        current = text.splitlines()
        missing = [line for line in lines if line.strip() and line not in current]
        assert not missing, f"{path}: existing lines were changed or removed: {missing[:3]}"


def test_missing_root_docs_not_created():
    for path in SPEC["absent"]:
        assert not (ROOT / path).exists(), f"{path} did not exist and must not be created"
