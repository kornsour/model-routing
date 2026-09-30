from toolbelt.iterutil import chunked, unique
from toolbelt.numbers import clamp, pct, safe_div
from toolbelt.text import slugify, squash_ws, truncate


def test_slugify():
    assert slugify("Héllo, World!") == "hello-world"


def test_truncate():
    assert truncate("abcdefgh", 6) == "abc..."
    assert truncate("abc", 6) == "abc"


def test_squash():
    assert squash_ws("  a \n b\tc ") == "a b c"


def test_numbers():
    assert clamp(5, 0, 3) == 3
    assert safe_div(1, 0) == 0.0
    assert pct(1, 3) == "33.3%"
    assert pct(1, 0) == "n/a"


def test_iter():
    assert list(chunked(range(5), 2)) == [[0, 1], [2, 3], [4]]
    assert unique([3, 1, 3, 2, 1]) == [3, 1, 2]
