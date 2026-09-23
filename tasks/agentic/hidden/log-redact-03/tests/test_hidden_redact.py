from logproc.cli import main
from logproc.csvexport import import_csv

SECRETS = ["Hunter2x", "abc123", "eyJhbGciOi.eyJzdWIiOiIx.Sfl-KxwR_q", "s3cr3t/key+AA==", "zz9Q"]

LOG = (
    "2024-03-01T10:00:00 ERROR login failed user=bob Password=Hunter2x; retry=3\n"
    "2024-03-01T10:00:01 WARNING upstream said TOKEN=abc123 expired\n"
    "2024-03-01T10:00:02 ERROR bad session token=eyJhbGciOi.eyJzdWIiOiIx.Sfl-KxwR_q from gw\n"
    "2024-03-01T10:00:03 INFO GET /cb?client_secret=s3cr3t/key+AA==&state=ok\n"
    "2024-03-01T10:00:04 ERROR upstream 401 Authorization: Bearer zz9Q seen\n"
)

MASKED = [
    "login failed user=bob Password=***; retry=3",
    "upstream said TOKEN=*** expired",
    "bad session token=*** from gw",
    "GET /cb?client_secret=***&state=ok",
    "upstream 401 Authorization: Bearer *** seen",
]


def _process(tmp_path):
    log = tmp_path / "app.log"
    log.write_text(LOG)
    out = tmp_path / "entries.csv"
    assert main(["process", str(log), "--out", str(out)]) == 0
    return out


# Brief: "Nothing that section describes may reach the entries CSV written by `process` ...
# whatever the capitalization of the key and whatever characters the secret contains".
def test_process_csv_holds_no_secret(tmp_path):
    text = _process(tmp_path).read_text()
    for secret in SECRETS:
        assert secret not in text
    for fragment in ("Hunter", "eyJ", "s3cr3t", "zz9"):
        assert fragment not in text


# Brief: "... the rest of each message must come through unchanged" (README: only the secret
# itself is replaced by `***`).
def test_process_masks_exactly_the_secret(tmp_path):
    assert [e.message for e in import_csv(_process(tmp_path))] == MASKED


# Brief: "Nothing that section describes may reach ... the output of `errors`".
def test_errors_output_holds_no_secret(tmp_path, capsys):
    log = tmp_path / "app.log"
    log.write_text(LOG)
    assert main(["errors", str(log)]) == 0
    out = capsys.readouterr().out
    for secret in SECRETS:
        assert secret not in out
    assert "1  login failed user=bob Password=***; retry=3" in out.splitlines()
    assert "1  upstream 401 Authorization: Bearer *** seen" in out.splitlines()


# Brief: "messages that differ only in a masked secret are the same error and are counted
# together, listed once in masked form".
def test_errors_groups_messages_that_differ_only_in_a_secret(tmp_path, capsys):
    log = tmp_path / "app.log"
    log.write_text(
        "2024-03-01T10:00:00 ERROR db down\n"
        "2024-03-01T10:00:01 ERROR refresh failed access_token=AAA.1\n"
        "2024-03-01T10:00:02 ERROR db down\n"
        "2024-03-01T10:00:03 ERROR refresh failed access_token=BBB.2\n"
        "2024-03-01T10:00:05 ERROR refresh failed access_token=DDD.4\n"
    )
    assert main(["errors", str(log)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "3  refresh failed access_token=***",
        "2  db down",
    ]
