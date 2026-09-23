from notes import cli
from notes.dates import parse_due


def test_cli_no_longer_defines_its_own_parse_due():
    assert not hasattr(cli, "_parse_due")


def test_shared_helper_still_works():
    assert parse_due("2024-03-01").isoformat() == "2024-03-01"
