#!/usr/bin/env python3
"""Validate every agentic task: see ``model_routing.dispatch.validate``.

uv run python scripts/validate_agentic_tasks.py
"""

import sys

from model_routing.dispatch.validate import main

if __name__ == "__main__":
    sys.exit(main())
