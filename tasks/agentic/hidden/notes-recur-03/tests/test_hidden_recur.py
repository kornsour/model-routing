import json

from notes.cli import main
from notes.store import Store


def _add(db, text, due, repeat, *extra):
    argv = ["--db", str(db), "add", text, "--due", due, "--repeat", repeat, *extra]
    assert main(argv) == 0


def _complete_chain(db, times):
    """Complete the newest open to-do ``times`` times, one CLI invocation each."""
    dues = []
    for _ in range(times):
        open_notes = [n for n in Store(db).notes if not n.done]
        assert len(open_notes) == 1, [(n.id, n.due, n.done) for n in Store(db).notes]
        assert main(["--db", str(db), "done", str(open_notes[0].id)]) == 0
        dues.append(Store(db).notes[-1].due)
    return dues


# Brief: "`notes done` on a monthly to-do due 31 January ..." / Note.repeat: "Monthly ... to-dos
# stay on the day of the month they were first due: in a month too short for that day, the
# occurrence falls on the month's last day instead, and later occurrences go back to the
# original day" - "across separate `notes` invocations"
def test_monthly_from_31st_keeps_its_day(tmp_path):
    db = tmp_path / "notes.json"
    _add(db, "Pay rent", "2024-01-31", "monthly")
    assert _complete_chain(db, 5) == [
        "2024-02-29",
        "2024-03-31",
        "2024-04-30",
        "2024-05-31",
        "2024-06-30",
    ]


# Brief: "for every repeat kind and any due date" (month and year ends)
def test_monthly_across_year_end(tmp_path):
    db = tmp_path / "notes.json"
    _add(db, "Invoice client", "2024-11-30", "monthly")
    assert _complete_chain(db, 3) == ["2024-12-30", "2025-01-30", "2025-02-28"]


# Note.repeat: "Monthly and yearly to-dos stay on the day of the month they were first due"
def test_yearly_from_leap_day(tmp_path):
    db = tmp_path / "notes.json"
    _add(db, "Leap-day party", "2024-02-29", "yearly")
    assert _complete_chain(db, 4) == ["2025-02-28", "2026-02-28", "2027-02-28", "2028-02-29"]


# Brief: "for every repeat kind and any due date"
def test_daily_and_weekly_across_boundaries(tmp_path):
    db = tmp_path / "notes.json"
    _add(db, "Stand-up", "2024-12-31", "daily")
    assert _complete_chain(db, 2) == ["2025-01-01", "2025-01-02"]
    db2 = tmp_path / "weekly.json"
    _add(db2, "Bins out", "2024-02-26", "weekly")
    assert _complete_chain(db2, 1) == ["2024-03-04"]


# Brief: "the new occurrence often appears already ticked in `notes list`" / Note.repeat:
# "adds its next occurrence ... as a new, open to-do with the same text, tags and repeat"
def test_next_occurrence_is_open_copy(tmp_path, capsys):
    db = tmp_path / "notes.json"
    _add(db, "Water plants", "2024-03-15", "weekly", "--tag", "home,garden")
    assert main(["--db", str(db), "done", "1"]) == 0
    first, nxt = Store(db).notes
    assert first.done is True
    assert nxt.done is False
    assert nxt.id != first.id
    assert (nxt.text, nxt.tags, nxt.repeat, nxt.due) == (
        "Water plants",
        ["home", "garden"],
        "weekly",
        "2024-03-22",
    )
    capsys.readouterr()
    main(["--db", str(db), "list"])
    out = capsys.readouterr().out
    assert f"[ ] #{nxt.id} Water plants" in out
    assert "[x] #1 Water plants" in out


# Brief: "Completing a note that is already done must not change the store"
def test_completing_done_note_again_changes_nothing(tmp_path):
    db = tmp_path / "notes.json"
    _add(db, "Pay rent", "2024-01-31", "monthly")
    main(["--db", str(db), "done", "1"])
    before = db.read_bytes()
    main(["--db", str(db), "done", "1"])
    assert db.read_bytes() == before
    assert len(Store(db).notes) == 2


# Brief: "with store files written by the current version continuing to load and to repeat
# correctly"
def test_existing_store_file_keeps_working(tmp_path):
    db = tmp_path / "notes.json"
    db.write_text(
        json.dumps(
            [
                {"id": 1, "text": "Old note", "tags": [], "due": None, "done": False},
                {
                    "id": 2,
                    "text": "Pay rent",
                    "tags": ["bills"],
                    "due": "2024-01-31",
                    "done": False,
                    "repeat": "monthly",
                },
            ],
            indent=2,
        )
    )
    assert main(["--db", str(db), "done", "1"]) == 0
    assert main(["--db", str(db), "done", "2"]) == 0
    assert main(["--db", str(db), "done", "3"]) == 0
    notes = Store(db).notes
    assert [(n.id, n.due, n.done) for n in notes] == [
        (1, None, True),
        (2, "2024-01-31", True),
        (3, "2024-02-29", True),
        (4, "2024-03-31", False),
    ]
    assert notes[3].tags == ["bills"]
