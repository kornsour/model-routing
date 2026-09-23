from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def test_badge_is_passing():
    text = README.read_text()
    assert "build-failing" not in text
    assert "build-passing" in text
