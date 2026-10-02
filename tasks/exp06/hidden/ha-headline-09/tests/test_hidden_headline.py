"""Hidden grader: landing headline rewrite (exp06 stratum A, harvested brief)."""

import hashlib
import re
from pathlib import Path

ROOT = Path.cwd()
OLD = "Run your job search like a portfolio, not a lottery."
NEW = "Automate the busywork of building a career."
ALT = "Source roles. Score fit. Close skill gaps."
OLD_SUBHEAD_LEN = 274
MARKETING_SHA = "6c50ffb9b3635a1b507d8fac8118462814e197fe522adb7dad3c89299b5bf9b2"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _page() -> str:
    return (ROOT / "src/app/page.tsx").read_text()


def test_h1_is_the_new_headline():
    m = re.search(r"<h1[^>]*>(.*?)</h1>", _page(), re.S)
    assert m, "no <h1> in src/app/page.tsx"
    assert _norm(m.group(1)) == NEW


def test_alternative_kept_as_jsx_comment_above_h1():
    page = _page()
    h1_at = page.index("<h1")
    comments = [m for m in re.finditer(r"\{/\*(.*?)\*/\}", page, re.S) if m.end() <= h1_at]
    keeper = [m for m in comments if ALT in _norm(m.group(1))]
    assert keeper, "the alternative headline is not in a JSX comment above the h1"
    assert re.search(r"altern|kept|keep", keeper[-1].group(1), re.I), "no note saying it is a kept alternative"
    outside = re.sub(r"\{/\*.*?\*/\}", "", page, flags=re.S)
    assert ALT not in _norm(outside), "the alternative headline is rendered, not commented out"


def test_subhead_is_shorter_feature_forward_and_keeps_the_gate():
    page = _page()
    m = re.search(r"</h1>\s*<p[^>]*>(.*?)</p>", page, re.S)
    assert m, "no <p> subhead directly under the h1"
    sub = _norm(m.group(1))
    assert len(sub) < OLD_SUBHEAD_LEN, f"subhead not shorter than before ({len(sub)} chars)"
    assert re.search(r"skill|learn|grow|develop", sub, re.I), "subhead does not name the growth half"
    assert re.search(
        r"without passing your desk|passing your desk|without your (review|approval|sign-?off)|until you approve",
        sub,
        re.I,
    ), "subhead dropped the review-gate promise"
    assert "autonomous" not in sub.lower(), "subhead overstates autonomy"


def test_e2e_assertion_matches_new_h1_exactly():
    spec = (ROOT / "e2e/home.spec.ts").read_text()
    assert f'name: "{NEW}"' in spec
    assert "lottery" not in spec


def test_no_literal_copy_of_old_headline_left():
    hits = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if not path.is_file() or rel.parts[0] in (".git", "tests"):
            continue
        try:
            if OLD in path.read_text():
                hits.append(str(path.relative_to(ROOT)))
        except UnicodeDecodeError:
            continue
    assert not hits, f"old headline still present in {hits}"


def test_broader_prose_left_alone():
    marketing = ROOT / "src/content/marketing.ts"
    assert hashlib.sha256(marketing.read_bytes()).hexdigest() == MARKETING_SHA
    assert "self-hosted job-search assistant" in (ROOT / "README.md").read_text()
