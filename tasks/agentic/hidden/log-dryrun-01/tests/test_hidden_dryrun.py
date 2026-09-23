from logproc.cli import main


def test_dry_run_process_does_not_write_out(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("2024-03-01T10:00:00 INFO server started\n")
    out_path = tmp_path / "entries.csv"

    rc = main(["--dry-run", "process", str(log_path), "--out", str(out_path)])
    assert rc == 0
    assert not out_path.exists()
