"""Command-line entry point for the logproc tool."""

from __future__ import annotations

import argparse
import sys

from logproc.follow import follow_once
from logproc.pipeline import EntryWriter, build_report, process_log


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="logproc")
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help="(legacy) print the report as JSON; no longer implemented",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    process = sub.add_parser("process", help="parse a log file and print a summary report")
    process.add_argument("log_path")
    process.add_argument("--out", default="entries.csv")

    report = sub.add_parser("report", help="summarize an already-written entries CSV")
    report.add_argument("out_path")

    follow = sub.add_parser("follow", help="append entries logged since the last run")
    follow.add_argument("log_path")
    follow.add_argument("--state", required=True)
    follow.add_argument("--out", default="entries.csv")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "process":
        writer = process_log(args.log_path, args.out)
        writer.close()
        summary = build_report(args.out)
        print(f"{summary['count']} entries: {summary['by_level']}")
        return 0

    if args.command == "report":
        summary = build_report(args.out_path)
        print(f"{summary['count']} entries: {summary['by_level']}")
        return 0

    if args.command == "follow":
        writer = EntryWriter(args.out)
        count = follow_once(args.log_path, args.state, writer)
        print(f"{count} new entries")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
