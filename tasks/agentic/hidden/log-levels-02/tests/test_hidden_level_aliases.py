import pytest
from logproc.cli import main
from logproc.parser import parse_line
from logproc.pipeline import build_report, process_log

GATEWAY_LOG = (
    "2024-03-01T10:00:00 INFO listening\n"
    "2024-03-01T10:00:01 WARN upstream slow\n"
    "2024-03-01T10:00:02 WARN upstream slow\n"
    "2024-03-01T10:00:03 ERR upstream down\n"
    "2024-03-01T10:00:04 FATAL giving up\n"
    "2024-03-01T10:00:05 SEVERE batch aborted\n"
    "2024-03-01T10:00:06 TRACE noise\n"
    "2024-03-01T10:00:07 NOTICE noise\n"
    "2024-03-01T10:00:08 DEBUG detail\n"
)
EXPECTED = {"INFO": 1, "WARNING": 2, "ERROR": 1, "CRITICAL": 2, "DEBUG": 1}


# Brief / README: "count every line under its canonical documented level, whatever spelling
# the service used" - the parser reports the canonical name.
@pytest.mark.parametrize(
    "raw, canonical",
    [("WARN", "WARNING"), ("ERR", "ERROR"), ("FATAL", "CRITICAL"), ("SEVERE", "CRITICAL")],
)
def test_parse_line_canonicalizes_aliases(raw, canonical):
    entry = parse_line(f"2024-03-01T10:00:00 {raw} something happened")
    assert entry is not None
    assert entry.level == canonical
    assert entry.message == "something happened"


# Brief: "lines whose level is not documented at all must be skipped rather than counted (the
# parser docstring already says so)".
@pytest.mark.parametrize("raw", ["TRACE", "NOTICE", "VERBOSE", "Info"])
def test_parse_line_skips_undocumented_levels(raw):
    assert parse_line(f"2024-03-01T10:00:00 {raw} something happened") is None


# Brief: canonical levels themselves are unchanged.
def test_parse_line_keeps_canonical_levels():
    assert parse_line("2024-03-01T10:00:00 CRITICAL x").level == "CRITICAL"
    assert parse_line("2024-03-01T10:00:00 WARNING x").level == "WARNING"


# Brief: the symptom - a fresh `process` of the gateway log must give canonical counts.
def test_process_gateway_log_counts_canonically(tmp_path):
    log = tmp_path / "gateway.log"
    log.write_text(GATEWAY_LOG)
    out = tmp_path / "entries.csv"
    process_log(log, out).close()
    assert build_report(out)["by_level"] == EXPECTED


# Brief: "entries CSVs written by earlier runs still hold the raw spellings, and `report` on
# those files must produce the same canonical counts as a fresh `process` would".
def test_report_on_old_csv_with_raw_spellings(tmp_path):
    out = tmp_path / "entries.csv"
    out.write_text(
        "timestamp,level,message\n"
        "2024-03-01T10:00:00,INFO,listening\n"
        "2024-03-01T10:00:01,WARN,upstream slow\n"
        "2024-03-01T10:00:02,WARN,upstream slow\n"
        "2024-03-01T10:00:03,ERR,upstream down\n"
        "2024-03-01T10:00:04,FATAL,giving up\n"
        "2024-03-01T10:00:05,SEVERE,batch aborted\n"
        "2024-03-01T10:00:08,DEBUG,detail\n"
    )
    summary = build_report(out)
    assert summary["count"] == 7
    assert summary["by_level"] == EXPECTED


# Brief: the `report` command on such a file (the user-facing surface) prints canonical counts.
def test_cli_report_on_old_csv(tmp_path, capsys):
    out = tmp_path / "entries.csv"
    out.write_text(
        "timestamp,level,message\n2024-03-01T10:00:01,WARN,a\n2024-03-01T10:00:02,ERR,b\n"
    )
    assert main(["report", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "'WARNING': 1" in printed
    assert "'ERROR': 1" in printed
    assert "WARN'" not in printed.replace("WARNING'", "")
