from datetime import date

from notes.cli import main
from notes.recur import next_due
from notes.store import Store


def test_next_due_daily_and_weekly():
    assert next_due(date(2024, 3, 1), "daily") == date(2024, 3, 2)
    assert next_due(date(2024, 3, 1), "weekly") == date(2024, 3, 8)


def test_next_due_monthly_mid_month():
    assert next_due(date(2024, 3, 15), "monthly") == date(2024, 4, 15)


def test_done_on_weekly_todo_adds_next_occurrence(tmp_path, capsys):
    db = str(tmp_path / "notes.json")
    assert (
        main(["--db", db, "add", "Water plants", "--due", "2024-03-01", "--repeat", "weekly"]) == 0
    )
    assert main(["--db", db, "done", "1"]) == 0
    notes = Store(db).notes
    assert len(notes) == 2
    assert notes[0].done is True
    assert notes[1].due == "2024-03-08"
    assert notes[1].text == "Water plants"


def test_done_on_one_off_note(tmp_path):
    db = str(tmp_path / "notes.json")
    main(["--db", db, "add", "Buy milk"])
    assert main(["--db", db, "done", "1"]) == 0
    assert [n.done for n in Store(db).notes] == [True]
