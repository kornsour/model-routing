"""Hidden grader: archive convention (exp06 stratum A, harvested brief)."""

import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
SPEC = json.loads('{"archive": "archive", "wrong_archive": "docs/archive", "moved": {}, "kept": {"docs/conventions.md": "d25d335fbb76733840b7bdb517bebe97612d26aa5408fe581c2ad4bda83ff880", "CHANGELOG.md": "4e24be18ddd3630b8db7467b92263533ff547d69fb559111b80bcd283a876db8"}, "noted": {"README.md": ["# ts-starter", "", "A minimal TypeScript starter for new services and libraries. Click **Use this", "template** on GitHub, then rename the package in `package.json`.", "", "## What you get", "", "- Strict `tsconfig.json` and type-stripped execution on Node 24 (no build step for tests).", "- `node --test` for unit tests, colocated as `*.test.ts`.", "- Biome for lint and format.", "- A CI workflow that calls the shared reusable workflow.", "", "## Layout", "", "```", "src/            library code and colocated tests", "docs/           conventions for repos created from this template", ".github/        CI caller stub", "```", "", "## Commands", "", "```bash", "npm test        # node --test", "npm run check   # biome", "```"], "CLAUDE.md": ["# CLAUDE.md", "", "This is a template repository. Changes here are inherited by every repo", "created from it, so keep it small and generic.", "", "- Tests are colocated `*.test.ts` files run by `node --test`.", "- Keep runtime dependencies at zero.", "- Conventions for derived repos live in `docs/conventions.md`."], "AGENTS.md": ["# AGENTS.md", "", "Instructions for coding agents.", "", "1. Run `npm test` before you finish.", "2. Do not add dependencies to the template.", "3. Prefer editing `docs/conventions.md` over adding new top-level docs."]}, "absent": []}')


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
