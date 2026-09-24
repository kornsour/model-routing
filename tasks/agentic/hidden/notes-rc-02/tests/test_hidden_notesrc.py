from notes.cli import main
from notes.config import load_config
from notes.store import Store


def _rc(tmp_path, text):
    rc = tmp_path / ".notesrc"
    rc.write_text(text)
    return rc


# Brief: "`option = value` or `option: value` lines"
def test_colon_delimiter(tmp_path):
    rc = _rc(tmp_path, "[notes]\ndb: work.json\npage_size = 4\n")
    assert load_config(rc)["notes"] == {"db": "work.json", "page_size": "4"}


# Brief: "whole-line comments starting with `;` or `#`"
def test_semicolon_and_hash_comments(tmp_path):
    rc = _rc(tmp_path, "; user defaults\n# more\n[notes]\n; inside a section\ndb = a.json\n")
    assert load_config(rc)["notes"] == {"db": "a.json"}


# Brief: "option names are case-insensitive"
def test_option_names_are_case_insensitive(tmp_path):
    rc = _rc(tmp_path, "[notes]\nPage_Size = 3\nDB = a.json\n")
    assert load_config(rc)["notes"]["page_size"] == "3"
    assert load_config(rc)["notes"]["db"] == "a.json"


# Brief: "`%(name)s` inside a value is replaced by that option from the same section
# or from `[DEFAULT]`"
def test_interpolation_from_default_section(tmp_path):
    rc = _rc(tmp_path, "[DEFAULT]\nhome = /srv/notes\n[notes]\ndb = %(home)s/work.json\n")
    assert load_config(rc)["notes"]["db"] == "/srv/notes/work.json"


# Brief: "every option in `[DEFAULT]` is inherited by every other section ... `DEFAULT`
# folded into each section rather than listed as a section of its own"
def test_default_section_is_inherited_not_listed(tmp_path):
    rc = _rc(tmp_path, "[DEFAULT]\npage_size = 2\n[notes]\ndb = a.json\n[other]\nx = 1\n")
    cfg = load_config(rc)
    assert cfg["notes"] == {"db": "a.json", "page_size": "2"}
    assert cfg["other"] == {"x": "1", "page_size": "2"}
    assert "DEFAULT" not in cfg


# Brief: "a value may continue on following indented lines" (tags reach `add` intact)
def test_continuation_lines_reach_add(tmp_path, capsys):
    db = tmp_path / "work.json"
    rc = _rc(tmp_path, f"[notes]\ndb = {db}\ntags = work,\n    urgent\n")
    assert main(["--rc", str(rc), "add", "Write report"]) == 0
    note = Store(db).notes[0]
    assert sorted(note.tags) == ["urgent", "work"]


# Brief: "a `page_size` set under `[DEFAULT]` must take effect on `list`; an explicit
# `--page-size` still wins"
def test_cli_page_size_inherited_from_default_section(tmp_path, capsys):
    db = tmp_path / "work.json"
    rc = _rc(tmp_path, f"[DEFAULT]\npage_size = 2\n[notes]\ndb = {db}\n")
    for text in ("a", "b", "c"):
        assert main(["--rc", str(rc), "add", text]) == 0
    capsys.readouterr()
    assert main(["--rc", str(rc), "list"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 2
    assert main(["--rc", str(rc), "list", "--page-size", "1"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 1
