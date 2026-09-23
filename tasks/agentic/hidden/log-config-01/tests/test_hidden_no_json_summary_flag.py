from pathlib import Path

import pytest
from logproc.cli import main

README = Path(__file__).resolve().parents[1] / "README.md"


def test_json_summary_flag_removed_from_readme():
    assert "json-summary" not in README.read_text()


def test_json_summary_flag_removed_from_cli(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("2024-03-01T10:00:00 INFO server started\n")
    with pytest.raises(SystemExit):
        main(["--json-summary", "process", str(log_path)])
