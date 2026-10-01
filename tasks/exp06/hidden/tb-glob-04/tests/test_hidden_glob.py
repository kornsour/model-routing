import pytest

from toolbelt.globmatch import match, select


@pytest.mark.parametrize(
    "pattern,path",
    [
        ("*.py", "setup.py"),
        ("src/*.py", "src/app.py"),
        ("src/?.py", "src/a.py"),
        ("**/*.py", "a.py"),
        ("**/*.py", "src/pkg/mod.py"),
        ("src/**/test_*.py", "src/test_x.py"),
        ("src/**/test_*.py", "src/a/b/c/test_x.py"),
        ("src/**", "src/a"),
        ("src/**", "src/a/b.txt"),
        ("**", "anything/at/all"),
        ("a/**/b/**/c", "a/b/c"),
        ("a/**/b/**/c", "a/x/b/y/z/c"),
        ("[abc].txt", "b.txt"),
        ("[a-c].txt", "b.txt"),
        ("[!a-c].txt", "d.txt"),
        ("[^a-c].txt", "d.txt"),
        ("[]x].txt", "].txt"),
        ("[a-].txt", "-.txt"),
        ("[-a].txt", "-.txt"),
        ("x[*]y", "x*y"),
        ("{a,b}.txt", "b.txt"),
        ("{src,lib}/**/*.{py,pyi}", "lib/pkg/types.pyi"),
        ("{a,{b,c}d}", "cd"),
        ("{,pre}fix", "fix"),
        ("{,pre}fix", "prefix"),
        ("{a/b,c}/d", "a/b/d"),
        ("file\\*.txt", "file*.txt"),
        ("\\{a,b\\}", "{a,b}"),
        ("a\\\\b", "a\\b"),
        ("{a", "{a"),
        ("a}", "a}"),
        ("[abc", "[abc"),
        ("a,b", "a,b"),
        ("{x}", "{x}"),
        (".hidden", ".hidden"),
        (".*", ".env"),
        ("src/.*/x", "src/.git/x"),
        ("a**b", "axyzb"),
        ("*", "a.b.c"),
        ("*.tar.gz", "pkg-1.0.tar.gz"),
        ("**/.cache/*", ".cache/x"),
    ],
)
def test_matches(pattern, path):
    assert match(pattern, path)


@pytest.mark.parametrize(
    "pattern,path",
    [
        ("*.py", "src/app.py"),
        ("src/*.py", "src/pkg/app.py"),
        ("src/?.py", "src/ab.py"),
        ("?", "/"),
        ("a?b", "a/b"),
        ("[a/]b", "/b"),
        ("src/**", "src"),
        ("**", ""),
        ("[!a-c].txt", "b.txt"),
        ("[abc].txt", "d.txt"),
        ("{a,b}.txt", "c.txt"),
        ("{a,b}.txt", "{a,b}.txt"),
        ("file\\*.txt", "fileX.txt"),
        ("*", ".env"),
        ("*.txt", ".txt"),
        ("?env", ".env"),
        ("[.]env", ".env"),
        ("**/*.py", ".venv/lib/x.py"),
        ("src/**/*.py", "src/.hidden/x.py"),
        ("**", "a/.b/c"),
        ("*/x", ".git/x"),
        ("a**b", "a/b"),
        ("Makefile", "makefile"),
        ("a/b", "a/b/c"),
        ("a/b/c", "a/b"),
    ],
)
def test_non_matches(pattern, path):
    assert not match(pattern, path)


def test_dot_option():
    assert match("*", ".env", dot=True)
    assert match("**/*.py", ".venv/lib/x.py", dot=True)
    assert match("?env", ".env", dot=True)
    assert match("src/**", "src/.a/.b", dot=True)


def test_ignore_case():
    assert match("Makefile", "makefile", ignore_case=True)
    assert match("*.PY", "a.py", ignore_case=True)
    assert match("[A-C].txt", "b.txt", ignore_case=True)
    assert not match("*.PY", "a.py")


def test_select_last_match_wins():
    paths = [
        "src/app.py",
        "src/test_app.py",
        "src/gen/out.py",
        "docs/index.md",
        "README.md",
        ".env",
        "!weird.txt",
    ]
    pats = ["**/*.py", "!**/test_*.py", "!src/gen/**", "*.md", "src/gen/keep*", "\\!weird.txt"]
    assert select(paths, pats) == ["src/app.py", "README.md", "!weird.txt"]
    assert select(paths, ["**", "!src/**"]) == ["docs/index.md", "README.md", "!weird.txt"]
    assert select(paths, ["**"], dot=True)[-2:] == [".env", "!weird.txt"]
    assert select(["x"], []) == []
    assert select(["a", "b"], ["!a"]) == []


def test_pathological_braces_and_stars_are_fast():
    import time

    t0 = time.perf_counter()
    assert not match("*a*a*a*a*a*a*a*a*a*a*a*b", "a" * 60)
    assert not match("**/**/**/**/**/**/x", "/".join(["d"] * 40))
    assert match("{a,b}{c,d}{e,f}{g,h}{i,j}{k,l}{m,n}", "bcfgjln")
    assert time.perf_counter() - t0 < 2.0
