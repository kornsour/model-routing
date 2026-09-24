"""Command-line entry point for the logproc tool."""

from __future__ import annotations

import argparse
import sys

from logproc.errors import format_errors, top_errors
from logproc.pipeline import build_report, process_log


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

    errors = sub.add_parser("errors", help="list the most frequent ERROR messages")
    errors.add_argument("log_path")
    errors.add_argument("--limit", type=int, default=10)

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

    if args.command == "errors":
        print(format_errors(top_errors(args.log_path, args.limit)))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
