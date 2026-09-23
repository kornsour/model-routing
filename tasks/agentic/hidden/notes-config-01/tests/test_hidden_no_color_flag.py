from pathlib import Path

import pytest
from notes.cli import main

README = Path(__file__).resolve().parents[1] / "README.md"


def test_color_flag_removed_from_readme():
    assert "color-output" not in README.read_text()


def test_color_flag_removed_from_cli(tmp_path):
    db = tmp_path / "notes.json"
    with pytest.raises(SystemExit):
        main(["--db", str(db), "--color-output", "add", "Buy milk"])
