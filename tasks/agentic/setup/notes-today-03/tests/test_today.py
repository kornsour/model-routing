from datetime import date

from notes import clock
from notes.agenda import agenda
from notes.cli import main
from notes.models import Note
from notes.remind import digest
from notes.search import filter_overdue


def test_filter_overdue_skips_future_and_done():
    notes = [
        Note(id=1, text="late", due="2024-03-01"),
        Note(id=2, text="later", due="2024-04-01"),
        Note(id=3, text="finished", due="2024-03-01", done=True),
        Note(id=4, text="undated"),
    ]
    assert [n.id for n in filter_overdue(notes, date(2024, 3, 10))] == [1]


def test_digest_groups():
    notes = [
        Note(id=1, text="late", due="2024-03-01"),
        Note(id=2, text="soon", due="2024-03-11"),
        Note(id=3, text="far", due="2024-04-01"),
    ]
    assert digest(notes, date(2024, 3, 10)) == ["overdue: #1 late", "tomorrow: #2 soon"]


def test_agenda_groups_by_day(monkeypatch):
    monkeypatch.setattr(clock, "_override", date(2024, 3, 10))
    notes = [
        Note(id=1, text="a", due="2024-03-12"),
        Note(id=2, text="b", due="2024-03-11"),
        Note(id=3, text="c", due="2024-03-12"),
        Note(id=4, text="d", due="2024-05-01"),
    ]
    result = agenda(notes, days=3)
    assert [(day.isoformat(), [n.id for n in items]) for day, items in result] == [
        ("2024-03-11", [2]),
        ("2024-03-12", [1, 3]),
    ]


def test_agenda_command_runs(tmp_path, capsys):
    db = str(tmp_path / "notes.json")
    main(["--db", db, "add", "Dentist", "--due", "2024-03-12"])
    capsys.readouterr()
    assert main(["--db", db, "--today", "2024-03-10", "agenda"]) == 0
    assert capsys.readouterr().out == "2024-03-12\n  #1 Dentist\n"
