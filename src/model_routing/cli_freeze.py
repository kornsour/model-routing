"""Freeze and unfreeze Claude Code auto-updates around a paid experiment run.

    make cli-freeze      # before a run: no background updates
    make cli-unfreeze    # after the run: updates back on
    make cli-status

A registered run must use one Claude Code version from start to finish, but
the native installer updates itself in the background. Freezing sets
``DISABLE_AUTOUPDATER=1`` in the ``env`` of ``~/.claude/settings.json``, the
documented switch (code.claude.com/docs/en/setup#disable-auto-updates); it
stops the background check and leaves ``claude update`` working. The dispatch
runner also sets the variable on every CLI session it starts, because those
sessions run with ``--setting-sources ""`` and never read user settings.

Unfreeze after every experiment: staying current is itself worth money (the
5.5 generation cost about 30% of 5.0 on the same tasks in exp06).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

VAR = "DISABLE_AUTOUPDATER"
SETTINGS = Path.home() / ".claude" / "settings.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text().strip()
    return json.loads(text) if text else {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def is_frozen(path: Path = SETTINGS) -> bool:
    return str((_load(path).get("env") or {}).get(VAR, "")) == "1"


def freeze(path: Path = SETTINGS) -> bool:
    """Turn background auto-updates off. Returns True if anything changed."""
    data = _load(path)
    env = dict(data.get("env") or {})
    if env.get(VAR) == "1":
        return False
    env[VAR] = "1"
    data["env"] = env
    _save(path, data)
    return True


def unfreeze(path: Path = SETTINGS) -> bool:
    """Turn background auto-updates back on. Returns True if anything changed."""
    data = _load(path)
    env = dict(data.get("env") or {})
    if VAR not in env:
        return False
    del env[VAR]
    if env:
        data["env"] = env
    else:
        data.pop("env", None)
    _save(path, data)
    return True


def cli_version() -> str | None:
    binary = shutil.which("claude")
    if not binary:
        return None
    try:
        out = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Freeze or unfreeze Claude Code auto-updates.")
    ap.add_argument("action", choices=["freeze", "unfreeze", "status"])
    args = ap.parse_args(argv)
    if args.action == "freeze":
        changed = freeze()
        print(("froze" if changed else "already frozen") + f": {VAR}=1 in {SETTINGS}")
    elif args.action == "unfreeze":
        changed = unfreeze()
        print(("unfroze" if changed else "already unfrozen") + f": {VAR} removed from {SETTINGS}")
    state = "frozen (auto-update off)" if is_frozen() else "auto-update on"
    print(f"{state}; claude {cli_version() or 'not found'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
