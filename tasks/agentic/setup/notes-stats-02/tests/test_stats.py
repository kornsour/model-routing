from notes.cli import main
from notes.models import Note
from notes.stats import summary, tag_counts


def test_summary_counts_done_and_open():
    notes = [Note(id=1, text="a", done=True), Note(id=2, text="b")]
    assert summary(notes) == {"total": 2, "done": 1, "open": 1}


def test_tag_counts_most_common_first():
    notes = [
        Note(id=1, text="a", tags=["errand"]),
        Note(id=2, text="b", tags=["errand", "home"]),
        Note(id=3, text="c", tags=["home", "work"]),
    ]
    assert list(tag_counts(notes).items()) == [("errand", 2), ("home", 2), ("work", 1)]


def test_stats_command(tmp_path, capsys):
    db = tmp_path / "notes.json"
    assert main(["--db", str(db), "add", "Buy milk", "--tag", "errand"]) == 0
    capsys.readouterr()
    assert main(["--db", str(db), "stats"]) == 0
    out = capsys.readouterr().out
    assert "total: 1" in out
    assert "  errand: 1" in out
