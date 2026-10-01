"""Make every package's in-tree ``src`` importable without an install step."""

import sys
from pathlib import Path

for src in sorted((Path(__file__).resolve().parent / "packages").glob("*/src")):
    sys.path.insert(0, str(src))
