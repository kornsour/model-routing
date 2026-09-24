"""Command-line entry point for the logproc tool."""

from __future__ import annotations

import argparse
import sys

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
    report.add_argument("--since", default=None, help="only entries at or after this timestamp")
    report.add_argument("--until", default=None, help="only entries before this timestamp")

    return parser


def _print_summary(summary: dict) -> None:
    span = f" ({summary['first']} .. {summary['last']})" if summary["count"] else ""
    print(f"{summary['count']} entries: {summary['by_level']}{span}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "process":
        writer = process_log(args.log_path, args.out)
        writer.close()
        _print_summary(build_report(args.out))
        return 0

    if args.command == "report":
        _print_summary(build_report(args.out_path, since=args.since, until=args.until))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
