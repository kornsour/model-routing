from datetime import date, timedelta

from notes.cli import main
from notes.store import Store


def _store(tmp_path, dues):
    db = tmp_path / "notes.json"
    store = Store(db)
    for text, due in dues:
        store.add(text, due=due)
    return db


def _run(capsys, db, *argv):
    capsys.readouterr()
    assert main(["--db", str(db), *argv]) == 0
    return capsys.readouterr().out


MARCH = [
    ("long overdue", "2024-03-01"),
    ("yesterday", "2024-03-09"),
    ("today", "2024-03-10"),
    ("tomorrow", "2024-03-11"),
    ("day after", "2024-03-12"),
    ("sixth day", "2024-03-16"),
    ("eighth day", "2024-03-17"),
]


# Brief: "a note due on the day itself is due today, not overdue; overdue means due strictly
# before today and not done"
def test_list_overdue_excludes_due_today(tmp_path, capsys):
    db = _store(tmp_path, MARCH)
    Store(db).mark_done(1)
    out = _run(capsys, db, "--today", "2024-03-10", "list", "--overdue")
    assert out == "[ ] #2 yesterday\n"


# Brief: "`remind` must list each open to-do at most once, in the group the `notes.remind`
# docstring gives it" + "`--today` ... every date-relative command"
def test_remind_honours_today_option(tmp_path, capsys):
    db = _store(tmp_path, MARCH)
    out = _run(capsys, db, "--today", "2024-03-10", "remind")
    assert out.splitlines() == [
        "overdue: #1 long overdue",
        "overdue: #2 yesterday",
        "today: #3 today",
        "tomorrow: #4 tomorrow",
    ]


# Brief: "`--today` ... must make every date-relative command behave as if it were that day"
# (two invocations, two different days)
def test_remind_follows_each_invocations_today(tmp_path, capsys):
    db = _store(tmp_path, MARCH)
    first = _run(capsys, db, "--today", "2024-03-11", "remind")
    second = _run(capsys, db, "--today", "2024-03-16", "remind")
    assert first.splitlines() == [
        "overdue: #1 long overdue",
        "overdue: #2 yesterday",
        "overdue: #3 today",
        "today: #4 tomorrow",
        "tomorrow: #5 day after",
    ]
    assert second.splitlines()[-2:] == ["today: #6 sixth day", "tomorrow: #7 eighth day"]
    assert len(second.splitlines()) == 7


# Brief: "without `--today` they use the real local date"
def test_remind_without_option_uses_real_date(tmp_path, capsys):
    real = date.today()
    db = _store(
        tmp_path,
        [
            ("real today", real.isoformat()),
            ("real tomorrow", (real + timedelta(days=1)).isoformat()),
        ],
    )
    _run(capsys, db, "--today", "2001-01-01", "remind")
    out = _run(capsys, db, "remind")
    assert out.splitlines() == ["today: #1 real today", "tomorrow: #2 real tomorrow"]


# Brief: "`agenda --days N` covers N calendar days starting with today (the `notes.agenda`
# docstring)"
def test_agenda_window_is_n_days(tmp_path, capsys):
    db = _store(tmp_path, MARCH)
    out = _run(capsys, db, "--today", "2024-03-10", "agenda")
    days = [line for line in out.splitlines() if not line.startswith(" ")]
    assert days == ["2024-03-10", "2024-03-11", "2024-03-12", "2024-03-16"]
    out = _run(capsys, db, "--today", "2024-03-10", "agenda", "--days", "1")
    assert out == "2024-03-10\n  #3 today\n"
    out = _run(capsys, db, "--today", "2024-03-11", "agenda", "--days", "2")
    assert out == "2024-03-11\n  #4 tomorrow\n2024-03-12\n  #5 day after\n"
