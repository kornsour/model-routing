"""Every local href in the site points at a file that exists."""

import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


def test_local_links_resolve():
    for page in SITE.rglob("*.html"):
        for href in re.findall(r'href="([^"#:]+)"', page.read_text()):
            assert (page.parent / href).exists(), f"{page.name} -> {href}"
