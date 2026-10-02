"""Runs the golden set through the agent and fails below the threshold."""

import json
import sys
from pathlib import Path

from triage.agent import triage_ticket
from triage.audit import AuditLog

THRESHOLD = 0.85


def main() -> int:
    cases = json.loads((Path(__file__).parent / "golden.json").read_text())
    hits = sum(1 for c in cases if c["expect_source"] in triage_ticket(c["ticket"], AuditLog())["sources"])
    score = hits / len(cases)
    print(f"eval score {score:.2f} (threshold {THRESHOLD})")
    return 0 if score >= THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(main())
