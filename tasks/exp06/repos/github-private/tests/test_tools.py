import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_tools_parse():
    for script in (ROOT / "tools").glob("*.sh"):
        assert subprocess.run(["bash", "-n", str(script)]).returncode == 0, script
