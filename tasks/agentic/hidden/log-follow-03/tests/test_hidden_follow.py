import contextlib

import pytest
from logproc.cli import main
from logproc.csvexport import import_csv
from logproc.pipeline import EntryWriter


def _run(log, state, out):
    return main(["follow", str(log), "--state", str(state), "--out", str(out)])


def _messages(out):
    return [e.message for e in import_csv(out)] if out.exists() else []


@pytest.fixture
def paths(tmp_path):
    return tmp_path / "app.log", tmp_path / "app.state", tmp_path / "entries.csv"


# Brief: "A first run with no state file processes the whole log."
def test_first_run_processes_whole_log(paths):
    log, state, out = paths
    log.write_text("2024-03-01T10:00:00 INFO a\n2024-03-01T10:00:01 INFO b\n")
    _run(log, state, out)
    assert _messages(out) == ["a", "b"]


# Brief: "a line the service has only partly written when a run starts must be picked up
# whole by a later run once it is complete (never truncated, never skipped)".
def test_partial_last_line_is_picked_up_whole_later(paths):
    log, state, out = paths
    log.write_text("2024-03-01T10:00:00 INFO a\n2024-03-01T10:00:01 ERROR disk fu")
    _run(log, state, out)
    assert _messages(out) == ["a"]
    with log.open("a") as fh:
        fh.write("ll on /var\n2024-03-01T10:00:02 INFO c\n")
    _run(log, state, out)
    assert _messages(out) == ["a", "disk full on /var", "c"]


# Brief: same sentence - a line cut before its level is complete must not be lost either.
def test_partial_line_cut_inside_timestamp(paths):
    log, state, out = paths
    log.write_text("2024-03-01T10:00:00 INFO a\n2024-03-01T10:0")
    _run(log, state, out)
    with log.open("a") as fh:
        fh.write("0:01 WARNING slow\n")
    _run(log, state, out)
    _run(log, state, out)
    assert _messages(out) == ["a", "slow"]


def _rotate(log, new_text):
    log.rename(log.with_name("app.log.1"))
    log.write_text(new_text)


# Brief: "after the log is rotated, the fresh file must be read from its first line ...
# without re-processing anything from before the rotation".
def test_rotation_to_shorter_file(paths):
    log, state, out = paths
    log.write_text("".join(f"2024-03-01T10:00:0{i} INFO old{i}\n" for i in range(5)))
    _run(log, state, out)
    _rotate(log, "2024-03-01T11:00:00 INFO new0\n")
    _run(log, state, out)
    assert _messages(out) == [f"old{i}" for i in range(5)] + ["new0"]


# Brief: "... also when it has already grown longer than the old file was by the time the
# next run happens".
def test_rotation_to_file_already_longer_than_old_offset(paths):
    log, state, out = paths
    log.write_text("2024-03-01T10:00:00 INFO old0\n")
    _run(log, state, out)
    new = [f"new{i}" for i in range(6)]
    _rotate(log, "".join(f"2024-03-01T11:00:0{i} INFO {m}\n" for i, m in enumerate(new)))
    _run(log, state, out)
    assert _messages(out) == ["old0", *new]
    _run(log, state, out)
    assert _messages(out) == ["old0", *new]


# Brief: "a run that fails before its entries are safely in the CSV must leave things so the
# next run picks those lines up again" (every complete line reaches the CSV exactly once).
def test_failed_flush_does_not_lose_lines(paths, monkeypatch):
    log, state, out = paths
    log.write_text("2024-03-01T10:00:00 INFO a\n")
    _run(log, state, out)
    with log.open("a") as fh:
        fh.write("2024-03-01T10:00:01 ERROR b\n2024-03-01T10:00:02 INFO c\n")

    def disk_full(self):
        raise OSError(28, "No space left on device")

    with monkeypatch.context() as m:
        m.setattr(EntryWriter, "close", disk_full)
        with contextlib.suppress(OSError):
            _run(log, state, out)

    _run(log, state, out)
    _run(log, state, out)
    assert _messages(out) == ["a", "b", "c"]
