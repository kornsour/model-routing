from logproc.cli import main


def test_process_prints_nonzero_summary(tmp_path, capsys):
    log_path = tmp_path / "app.log"
    log_path.write_text(
        "2024-03-01T10:00:00 INFO server started\n"
        "2024-03-01T10:00:01 ERROR boom\n"
        "2024-03-01T10:00:02 INFO still running\n"
    )
    out_path = tmp_path / "entries.csv"

    rc = main(["process", str(log_path), "--out", str(out_path)])
    assert rc == 0

    captured = capsys.readouterr()
    assert "3 entries" in captured.out
    assert out_path.exists()
