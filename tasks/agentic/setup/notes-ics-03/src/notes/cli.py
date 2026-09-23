"""Command-line entry point for the notes tool."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from notes.export import export_csv, import_csv
from notes.ics import export_ics, import_ics
from notes.models import Note
from notes.search import filter_done, filter_text, paginate
from notes.store import Store
from notes.tags import filter_tag, parse_tags

DEFAULT_DB = "notes.json"


def _parse_due(text: str) -> date:
    """Parse a ``--due`` date.

    Accepts the same ISO/US formats as ``notes.dates.parse_due``. Kept
    separate so the CLI can validate before ever touching the store.
    """
    text = text.strip()
    if "-" in text:
        y, m, d = text.split("-")
    elif "/" in text:
        m, d, y = text.split("/")
    else:
        raise ValueError(f"unrecognized date: {text!r}")
    return date(int(y), int(m), int(d))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="notes")
    parser.add_argument("--db", default=DEFAULT_DB, help="path to the JSON note store")
    parser.add_argument(
        "--color-output",
        action="store_true",
        help="(legacy) colorize output; no longer implemented",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="add a note")
    add.add_argument("text")
    add.add_argument("--tag", default="", help="comma-separated tags")
    add.add_argument("--due", default=None)

    listp = sub.add_parser("list", help="list notes, paginated")
    listp.add_argument("--page", type=int, default=1)
    listp.add_argument("--page-size", type=int, default=10)
    listp.add_argument("--done", action="store_true", help="only show completed notes")

    done = sub.add_parser("done", help="mark a note complete")
    done.add_argument("id", type=int)

    search = sub.add_parser("search", help="search note text")
    search.add_argument("query")

    tag = sub.add_parser("tag", help="list notes with a tag")
    tag.add_argument("tag")

    export = sub.add_parser("export", help="export all notes to CSV")
    export.add_argument("path")

    imp = sub.add_parser("import", help="bulk-import notes from CSV")
    imp.add_argument("path")

    ics_out = sub.add_parser("export-ics", help="export all notes as an iCalendar file")
    ics_out.add_argument("path")

    ics_in = sub.add_parser("import-ics", help="import to-dos from an iCalendar file")
    ics_in.add_argument("path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    store = Store(args.db)

    if args.command == "add":
        due = None
        if args.due:
            _parse_due(args.due)  # validate before saving
            due = args.due
        note = store.add(text=args.text, tags=parse_tags(args.tag), due=due)
        print(f"added note #{note.id}: {note.text}")
        return 0

    if args.command == "list":
        notes = filter_done(store.notes, args.done) if args.done else store.notes
        for note in paginate(notes, args.page, args.page_size):
            mark = "x" if note.done else " "
            print(f"[{mark}] #{note.id} {note.text}")
        return 0

    if args.command == "done":
        ok = store.mark_done(args.id)
        print(f"marked #{args.id} done" if ok else f"no such note: {args.id}")
        return 0 if ok else 1

    if args.command == "search":
        for note in filter_text(store.notes, args.query):
            print(f"#{note.id} {note.text}")
        return 0

    if args.command == "tag":
        for note in filter_tag(store.notes, args.tag):
            print(f"#{note.id} {note.text}")
        return 0

    if args.command == "export":
        export_csv(store.notes, args.path)
        print(f"exported {len(store.notes)} notes to {args.path}")
        return 0

    if args.command == "import":
        imported = import_csv(args.path)
        next_id = store.next_id()
        for note in imported:
            store.notes.append(Note(id=next_id, text=note.text, tags=note.tags, due=note.due))
            next_id += 1
        store.save()
        print(f"imported {len(imported)} notes from {args.path}")
        return 0

    if args.command == "export-ics":
        export_ics(store.notes, args.path)
        print(f"exported {len(store.notes)} notes to {args.path}")
        return 0

    if args.command == "import-ics":
        imported = import_ics(args.path)
        next_id = store.next_id()
        for note in imported:
            store.notes.append(
                Note(id=next_id, text=note.text, tags=note.tags, due=note.due, done=note.done)
            )
            next_id += 1
        store.save()
        print(f"imported {len(imported)} notes from {args.path}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
