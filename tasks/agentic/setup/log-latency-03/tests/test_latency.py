from logproc.cli import main
from logproc.fields import extract_duration, parse_duration


def test_parse_duration_units():
    assert parse_duration("12ms") == 12
    assert parse_duration("2s") == 2000


def test_extract_duration_absent():
    assert extract_duration("GET /health ok") is None


def test_latency_single_request(tmp_path, capsys):
    log = tmp_path / "app.log"
    log.write_text("2024-03-01T10:00:00 INFO GET /a took=40ms\n2024-03-01T10:00:01 INFO idle\n")
    assert main(["latency", str(log)]) == 0
    assert capsys.readouterr().out.strip() == "count=1 p50=40 p90=40 p99=40 max=40"
