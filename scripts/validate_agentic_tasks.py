#!/usr/bin/env python3
"""Validate every agentic task: see ``model_routing.dispatch.validate``.

uv run python scripts/validate_agentic_tasks.py [TASKS_JSONL ...]
"""

import sys
from pathlib import Path

from model_routing.dispatch.validate import main

if __name__ == "__main__":
    paths = [Path(a) for a in sys.argv[1:]]
    sys.exit(max((main(p) for p in paths), default=0) if paths else main())
