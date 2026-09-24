from logproc.cli import main
from logproc.redact import redact


def test_redact_password():
    assert redact("login ok password=hunter2 user=bob") == "login ok password=*** user=bob"


def test_errors_lists_most_frequent_first(tmp_path, capsys):
    log = tmp_path / "app.log"
    log.write_text(
        "2024-03-01T10:00:00 ERROR db down\n"
        "2024-03-01T10:00:01 INFO ok\n"
        "2024-03-01T10:00:02 ERROR cache miss storm\n"
        "2024-03-01T10:00:03 ERROR cache miss storm\n"
    )
    assert main(["errors", str(log)]) == 0
    assert capsys.readouterr().out.splitlines() == ["2  cache miss storm", "1  db down"]
