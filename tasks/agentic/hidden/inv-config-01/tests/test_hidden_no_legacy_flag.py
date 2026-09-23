from pathlib import Path

import pytest
from invoicing.cli import main

README = Path(__file__).resolve().parents[1] / "README.md"


def test_legacy_flag_removed_from_readme():
    assert "legacy-tax-table" not in README.read_text()


def test_legacy_flag_removed_from_cli(tmp_path):
    db = tmp_path / "invoices.json"
    with pytest.raises(SystemExit):
        main(["--db", str(db), "--legacy-tax-table", "report"])
