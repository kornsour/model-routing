"""Reproduce the stratum-A draw order for the exp06 Stage 0 extension.

    uv run python tasks/exp06/harvest_draw.py [HARVESTED_JSONL] [N]

Sorts the harvested handoffs (``make harvest-chips``) by id and shuffles them
with ``random.Random(SEED)``; prompts are then reviewed in that order until 16
are accepted (see ``harvest_draw.json`` for each decision). Prints positions,
ids, kinds and word counts only - never prompt text (the harvest is private).
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

SEED = 20261001
DEFAULT = Path("tasks/agentic/private/harvested.jsonl")


def draw_order(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows.sort(key=lambda r: r["id"])
    random.Random(SEED).shuffle(rows)
    return rows


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    for i, r in enumerate(draw_order(path)[:n]):
        print(f"{i:3d} {r['id']} {r['kind']:<8} {r['prompt_words']:>5} words")


if __name__ == "__main__":
    main()
