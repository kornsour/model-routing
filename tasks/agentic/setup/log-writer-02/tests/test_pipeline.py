from logproc.pipeline import build_report, process_log, process_logs


def test_process_then_report(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("2024-03-01T10:00:00 INFO server started\n2024-03-01T10:00:01 ERROR boom\n")
    out_path = tmp_path / "entries.csv"

    writer = process_log(log_path, out_path)
    writer.close()  # must flush before build_report can see the entries
    summary = build_report(out_path)

    assert summary["count"] == 2
    assert summary["by_level"] == {"INFO": 1, "ERROR": 1}


def test_process_logs_single_file(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("2024-03-01T10:00:00 INFO server started\n")
    out_path = tmp_path / "entries.csv"

    writer = process_logs([log_path], out_path)
    writer.close()
    assert build_report(out_path)["count"] == 1
