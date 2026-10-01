"""Hidden grader: archive convention (exp06 stratum A, harvested brief)."""

import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
SPEC = json.loads('{"archive": "docs/archive", "wrong_archive": "archive", "moved": {"docs/tts-provider-polly.md": "ca1752ec250e3e1b1f9e749dfc24405c395382ad3c0c88c448985f1abde66b94", "docs/setup-once-voices-bucket.md": "b99361b894e808fbe87dd032e77759d69c1d4451e3374e7e6fb7a8bef0599435"}, "kept": {"docs/tts.md": "8d7f0c348da301ac921ba74ff323f08e50a0154250ff9f25a8b0f759d174868d", "docs/legacy-voices.md": "cfcdc17b82472433b0217a3fb76d4c04088b0bae28adae55df0b692d320a976b", "docs/chaptering.md": "671c083810a2ca34beea2e6302cd03eb8bacf69f8c9a4f7a0014bdbd0ac4e6a8", "docs/ideas.md": "55fc2ed695de9aa12abe54a0611dfe6cdf910b9954a9ff835627fef30704b9de"}, "noted": {"README.md": ["# narrator", "", "Turns an EPUB into a chaptered M4B audiobook with a local text-to-speech", "engine. Personal project; runs on a laptop, no cloud services.", "", "## Usage", "", "```bash", "python -m narrator book.epub --voice amber --out book.m4b", "```", "", "## Docs", "", "- `docs/tts.md` \\u2014 the TTS engine and how voices are configured.", "- `docs/legacy-voices.md` \\u2014 the legacy voice presets (still supported).", "- `docs/chaptering.md` \\u2014 how chapters and pauses are derived from the EPUB.", "- `docs/ideas.md` \\u2014 backlog."], "AGENTS.md": ["# AGENTS.md", "", "- Run `python -m pytest -q` before finishing.", "- The TTS engine is pluggable; never call a cloud API from tests.", "- Keep chapter detection deterministic: same EPUB in, same chapter list out."]}, "absent": ["CLAUDE.md"]}')


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
