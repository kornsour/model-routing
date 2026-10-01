"""``orchestra run pipeline.json`` - simulate a pipeline and print the result."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orchestra.model import JobSpec
from orchestra.scheduler import run


def _load(path: Path) -> tuple[list[JobSpec], dict[str, int]]:
    doc = json.loads(path.read_text())
    specs = [JobSpec.from_dict(j) for j in doc["jobs"]]
    return specs, dict(doc.get("capacities", {}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestra")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="simulate a pipeline")
    p_run.add_argument("pipeline", type=Path)
    args = parser.parse_args(argv)
    specs, caps = _load(args.pipeline)
    result = run(specs, caps)
    width = max((len(n) for n in result.runs), default=4)
    print(f"{'job':<{width}}  {'state':<15}  attempts  start  finish")
    for name, r in result.runs.items():
        start = "-" if r.started_at is None else f"{r.started_at:g}"
        finish = "-" if r.finished_at is None else f"{r.finished_at:g}"
        print(f"{name:<{width}}  {r.state.value:<15}  {r.attempts:>8}  {start:>5}  {finish:>6}")
    print(f"makespan: {result.makespan:g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
