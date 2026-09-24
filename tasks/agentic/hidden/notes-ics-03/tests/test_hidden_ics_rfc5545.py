import re

from notes.cli import main
from notes.ics import export_ics, import_ics
from notes.models import Note
from notes.store import Store

LONG_ASCII = "Renew the passport before the trip - " * 6
LONG_UTF8 = "Café crème " * 8 + "日本語のメモ" * 6 + " naïve résumé ✓" * 3
TRICKY = "Call Bob, then Alice; bring C:\\temp\\notes\nand the second line, too"


def _physical_lines(path):
    data = path.read_bytes()
    assert data.endswith(b"\r\n")
    return data[:-2].split(b"\r\n")


def _unfolded(path):
    lines = []
    for raw in _physical_lines(path):
        text = raw.decode("utf-8")
        if text[:1] in (" ", "\t"):
            lines[-1] += text[1:]
        else:
            lines.append(text)
    return lines


def _prop(lines, name):
    return [line.split(":", 1)[1] for line in lines if line.split(":", 1)[0].split(";")[0] == name]


# Brief: "content lines end in CRLF"
def test_every_line_ends_in_crlf(tmp_path):
    path = tmp_path / "out.ics"
    export_ics([Note(id=1, text="Buy milk", tags=["errand"], due="2024-03-01")], path)
    data = path.read_bytes()
    assert data.endswith(b"\r\n")
    assert re.search(rb"(?<!\r)\n", data) is None, "bare LF line ending"


# Brief: "lines longer than 75 octets are folded (CRLF + one space), never splitting a
# UTF-8 character"
def test_long_lines_folded_by_octets(tmp_path):
    path = tmp_path / "out.ics"
    export_ics([Note(id=1, text=LONG_ASCII), Note(id=2, text=LONG_UTF8)], path)
    raw_lines = _physical_lines(path)
    for raw in raw_lines:
        assert len(raw) <= 75, f"physical line of {len(raw)} octets"
        raw.decode("utf-8")  # a split multi-byte character would not decode on its own
    assert any(raw.startswith(b" ") for raw in raw_lines), "nothing was folded"
    summaries = _prop(_unfolded(path), "SUMMARY")
    assert summaries == [LONG_ASCII.replace(",", "\\,"), LONG_UTF8]


# Brief: "TEXT values (SUMMARY, each CATEGORIES value) are escaped as RFC 5545 requires"
def test_text_values_escaped(tmp_path):
    path = tmp_path / "out.ics"
    export_ics([Note(id=1, text=TRICKY, tags=["a,b", "x;y"])], path)
    lines = _unfolded(path)
    assert _prop(lines, "SUMMARY") == [
        "Call Bob\\, then Alice\\; bring C:\\\\temp\\\\notes\\nand the second line\\, too"
    ]
    assert _prop(lines, "CATEGORIES") == ["a\\,b,x\\;y"]


# Brief: "text containing backslashes, semicolons, commas or newlines - including a tag
# containing a comma - round-trips exactly"
def test_roundtrip_is_lossless(tmp_path):
    path = tmp_path / "out.ics"
    notes = [
        Note(id=1, text=TRICKY, tags=["a,b", "x;y", "back\\slash"], due="2024-03-01"),
        Note(id=2, text=LONG_UTF8, tags=["日本"], done=True),
        Note(id=3, text="ends with a backslash \\"),
    ]
    export_ics(notes, path)
    back = import_ics(path)
    assert [(n.text, n.tags, n.due, n.done) for n in back] == [
        (n.text, n.tags, n.due, n.done) for n in notes
    ]


FOREIGN = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Mozilla.org/NONSGML Mozilla Calendar V1.1//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:evt-1\r\n"
    "SUMMARY:Team offsite (an event, not a to-do)\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VTODO\r\n"
    "UID:1f0c3e\r\n"
    "DTSTAMP:20240220T101500Z\r\n"
    "summary;LANGUAGE=en-US:Prepare the quarterly report\\, including the appendix\r\n"
    "  and the budget\\; send to finance\\Nby Friday\r\n"
    "CATEGORIES:work\r\n"
    "Categories:reports,q1\\,draft\r\n"
    "DUE;VALUE=DATE:20240301\r\n"
    "X-MOZ-GENERATION:3\r\n"
    "STATUS:NEEDS-ACTION\r\n"
    "BEGIN:VALARM\r\n"
    "ACTION:EMAIL\r\n"
    "SUMMARY:Reminder mail subject\r\n"
    "DESCRIPTION:Reminder\r\n"
    "TRIGGER:-PT15M\r\n"
    "END:VALARM\r\n"
    "END:VTODO\r\n"
    "BEGIN:VTODO\r\n"
    "UID:2a9d\r\n"
    'SUMMARY;ALTREP="http://example.com/call-notes":Call the plumber\r\n'
    "STATUS:COMPLETED\r\n"
    "END:VTODO\r\n"
    "BEGIN:VTODO\r\n"
    "UID:3b7e\r\n"
    "SUMMARY:A long line folded with a tab by another app, which RFC 5545 al\r\n"
    "\tlows as well\r\n"
    "END:VTODO\r\n"
    "END:VCALENDAR\r\n"
)


# Brief: "On import, accept any valid RFC 5545 input for those properties: folded lines
# (space or tab continuation), escaped text (`\n` or `\N`), property names in any case,
# property parameters, repeated CATEGORIES lines, and the extra properties and components
# other apps write, which must be ignored"
def test_import_file_from_another_app(tmp_path):
    path = tmp_path / "thunderbird.ics"
    path.write_bytes(FOREIGN.encode("utf-8"))
    back = import_ics(path)
    assert [(n.text, n.tags, n.due, n.done) for n in back] == [
        (
            "Prepare the quarterly report, including the appendix and the budget; "
            "send to finance\nby Friday",
            ["work", "reports", "q1,draft"],
            "2024-03-01",
            False,
        ),
        ("Call the plumber", [], None, True),
        (
            "A long line folded with a tab by another app, which RFC 5545 allows as well",
            [],
            None,
            False,
        ),
    ]


# Brief: "A note exported and re-imported (through the `export-ics`/`import-ics` commands
# too) must come back with the same text, tags, due date and done flag"
def test_cli_roundtrip_between_stores(tmp_path):
    src = tmp_path / "src.json"
    store = Store(src)
    store.add(TRICKY, tags=["a,b", "home"], due="2024-03-01")
    store.add(LONG_UTF8, tags=["x;y"])
    store.mark_done(2)
    ics = tmp_path / "out.ics"
    assert main(["--db", str(src), "export-ics", str(ics)]) == 0

    dst = tmp_path / "dst.json"
    Store(dst).add("already here")
    assert main(["--db", str(dst), "import-ics", str(ics)]) == 0
    notes = Store(dst).notes
    assert [n.id for n in notes] == [1, 2, 3]
    assert [(n.text, n.tags, n.due, n.done) for n in notes[1:]] == [
        (TRICKY, ["a,b", "home"], "2024-03-01", False),
        (LONG_UTF8, ["x;y"], None, True),
    ]
