"""Command-line entry point for the logproc tool."""

from __future__ import annotations

import argparse
import sys

from logproc.aggregate import count_by_level
from logproc.pipeline import build_report, process_log, read_entries


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="logproc")
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help="(legacy) print the report as JSON; no longer implemented",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse and print the summary without writing --out to disk",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    process = sub.add_parser("process", help="parse a log file and print a summary report")
    process.add_argument("log_path")
    process.add_argument("--out", default="entries.csv")

    report = sub.add_parser("report", help="summarize an already-written entries CSV")
    report.add_argument("out_path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "process":
        if args.dry_run:
            entries = read_entries(args.log_path)
            summary = {"count": len(entries), "by_level": count_by_level(entries)}
            print(f"[dry-run] {summary['count']} entries: {summary['by_level']}")
            return 0
        writer = process_log(args.log_path, args.out)
        summary = build_report(args.out)
        writer.close()
        print(f"{summary['count']} entries: {summary['by_level']}")
        return 0

    if args.command == "report":
        summary = build_report(args.out_path)
        print(f"{summary['count']} entries: {summary['by_level']}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
