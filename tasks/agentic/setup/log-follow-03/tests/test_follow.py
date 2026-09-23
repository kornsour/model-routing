from logproc.cli import main
from logproc.csvexport import import_csv


def test_follow_picks_up_appended_lines(tmp_path):
    log = tmp_path / "app.log"
    state = tmp_path / "app.state"
    out = tmp_path / "entries.csv"
    log.write_text("2024-03-01T10:00:00 INFO started\n")
    assert main(["follow", str(log), "--state", str(state), "--out", str(out)]) == 0

    with log.open("a") as fh:
        fh.write("2024-03-01T10:00:01 ERROR boom\n")
    assert main(["follow", str(log), "--state", str(state), "--out", str(out)]) == 0

    assert [e.message for e in import_csv(out)] == ["started", "boom"]
