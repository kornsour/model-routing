from notes.cli import main
from notes.config import load_config, notes_defaults


def test_load_config_basic(tmp_path):
    rc = tmp_path / ".notesrc"
    rc.write_text("# defaults\n[notes]\ndb = work.json\npage_size = 5\n")
    assert load_config(rc) == {"notes": {"db": "work.json", "page_size": "5"}}


def test_notes_defaults_missing_file(tmp_path):
    assert notes_defaults(tmp_path / "nope") == {}


def test_cli_uses_db_and_tags_from_rc(tmp_path, capsys):
    rc = tmp_path / ".notesrc"
    db = tmp_path / "work.json"
    rc.write_text(f"[notes]\ndb = {db}\ntags = work\n")
    assert main(["--rc", str(rc), "add", "Write report"]) == 0
    assert main(["--rc", str(rc), "tag", "work"]) == 0
    assert "#1 Write report" in capsys.readouterr().out
