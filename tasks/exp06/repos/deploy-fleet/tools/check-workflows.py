#!/usr/bin/env python3
"""Parse every workflow file under the checked-out repos (the docs.yml check, run locally)."""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML missing: nothing to check with
    print("PyYAML not installed; skipping")
    sys.exit(0)

bad = 0
files = sorted(Path(".").glob("*/*/.github/workflows/*.yml"))
for path in files:
    try:
        yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        bad += 1
        print(f"{path}: {exc}")
print(f"{len(files)} workflow files, {bad} invalid")
sys.exit(1 if bad else 0)
