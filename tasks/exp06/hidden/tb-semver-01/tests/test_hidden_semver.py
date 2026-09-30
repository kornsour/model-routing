import pytest

from toolbelt.semver import (
    Version,
    max_satisfying,
    min_satisfying,
    normalize,
    parse_version,
    satisfies,
)


@pytest.mark.parametrize(
    "text,canon",
    [
        ("1.2.3", "1.2.3"),
        (" v1.2.3 ", "1.2.3"),
        ("=1.2.3", "1.2.3"),
        ("1.2.3-rc.1+build.5", "1.2.3-rc.1"),
        ("0.0.0-0", "0.0.0-0"),
        ("1.2.3-x-y.z", "1.2.3-x-y.z"),
    ],
)
def test_parse_valid(text, canon):
    assert str(parse_version(text)) == canon


@pytest.mark.parametrize(
    "text", ["1.2", "01.2.3", "1.02.3", "1.2.03", "1.2.3-01", "1.2.3-", "1.2.3+", "a.b.c", "1.2.3.4", ""]
)
def test_parse_invalid(text):
    with pytest.raises(ValueError):
        parse_version(text)


def test_precedence_chain():
    chain = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
        "1.0.1-0",
        "1.0.1",
        "1.10.0",
        "2.0.0",
    ]
    parsed = [parse_version(v) for v in chain]
    for a, b in zip(parsed, parsed[1:]):
        assert a < b, (a, b)
        assert not b < a
    assert sorted(reversed(parsed)) == parsed


def test_build_ignored_for_equality():
    assert parse_version("1.2.3+a") == parse_version("1.2.3+b")
    assert hash(parse_version("1.2.3+a")) == hash(parse_version("1.2.3"))
    assert parse_version("1.2.3-1") < parse_version("1.2.3-a")


@pytest.mark.parametrize(
    "rng,norm",
    [
        ("", ">=0.0.0"),
        ("*", ">=0.0.0"),
        ("1.x", ">=1.0.0 <2.0.0-0"),
        ("1.X", ">=1.0.0 <2.0.0-0"),
        ("1.*", ">=1.0.0 <2.0.0-0"),
        ("1", ">=1.0.0 <2.0.0-0"),
        ("1.2.x", ">=1.2.0 <1.3.0-0"),
        ("1.2", ">=1.2.0 <1.3.0-0"),
        ("=1.2", ">=1.2.0 <1.3.0-0"),
        ("1.2.3", "1.2.3"),
        ("=1.2.3", "1.2.3"),
        (">1", ">=2.0.0"),
        (">1.2", ">=1.3.0"),
        (">=1.2", ">=1.2.0"),
        ("<1.2", "<1.2.0-0"),
        ("<=1.2", "<1.3.0-0"),
        ("<1", "<1.0.0-0"),
        (">=*", ">=0.0.0"),
        ("<*", "<0.0.0-0"),
        (">*", "<0.0.0-0"),
        (">= 1.2.3", ">=1.2.3"),
        ("1.2.3 - 2.3.4", ">=1.2.3 <=2.3.4"),
        ("1.2 - 2.3.4", ">=1.2.0 <=2.3.4"),
        ("1.2.3 - 2.3", ">=1.2.3 <2.4.0-0"),
        ("1.2.3 - 2", ">=1.2.3 <3.0.0-0"),
        ("* - 2.0.0", ">=0.0.0 <=2.0.0"),
        ("1.2.3 - *", ">=1.2.3"),
        ("~1.2.3", ">=1.2.3 <1.3.0-0"),
        ("~1.2", ">=1.2.0 <1.3.0-0"),
        ("~1", ">=1.0.0 <2.0.0-0"),
        ("~0.2.3", ">=0.2.3 <0.3.0-0"),
        ("~0", ">=0.0.0 <1.0.0-0"),
        ("~1.2.3-beta.2", ">=1.2.3-beta.2 <1.3.0-0"),
        ("~>1.2.3", ">=1.2.3 <1.3.0-0"),
        ("^1.2.3", ">=1.2.3 <2.0.0-0"),
        ("^0.2.3", ">=0.2.3 <0.3.0-0"),
        ("^0.0.3", ">=0.0.3 <0.0.4-0"),
        ("^1.2.3-beta.2", ">=1.2.3-beta.2 <2.0.0-0"),
        ("^0.0.3-beta", ">=0.0.3-beta <0.0.4-0"),
        ("^1.2.x", ">=1.2.0 <2.0.0-0"),
        ("^1.2", ">=1.2.0 <2.0.0-0"),
        ("^0.0.x", ">=0.0.0 <0.1.0-0"),
        ("^0.0", ">=0.0.0 <0.1.0-0"),
        ("^1.x", ">=1.0.0 <2.0.0-0"),
        ("^1", ">=1.0.0 <2.0.0-0"),
        ("^0.x", ">=0.0.0 <1.0.0-0"),
        ("^0", ">=0.0.0 <1.0.0-0"),
        ("1.x || >=2.5.0 || 5.0.0 - 7.2.3", ">=1.0.0 <2.0.0-0||>=2.5.0||>=5.0.0 <=7.2.3"),
        ("^1.2.3 <1.5", ">=1.2.3 <2.0.0-0 <1.5.0-0"),
    ],
)
def test_normalize(rng, norm):
    assert normalize(rng) == norm


@pytest.mark.parametrize("rng", ["1.2.3 -2", ">>1.2.3", "^a.b", "1.2.3 - 2.3.4 - 5", "~1.2.3foo", ">=01.2.3"])
def test_invalid_range_raises(rng):
    with pytest.raises(ValueError):
        normalize(rng)
    with pytest.raises(ValueError):
        satisfies("1.2.3", rng)


@pytest.mark.parametrize(
    "version,rng",
    [
        ("1.2.3", "1.2.3"),
        ("1.2.3+build", "1.2.3"),
        ("0.2.9", "^0.2.3"),
        ("0.0.3", "^0.0.3"),
        ("1.2.3-beta.4", "^1.2.3-beta.2"),
        ("1.9.9", "^1.2.3"),
        ("2.3.9", "1.2.3 - 2.3"),
        ("2.9.9", "1.2.3 - 2"),
        ("1.2.3-alpha.7", ">1.2.3-alpha.3"),
        ("1.2.3", ">1.2.3-alpha.3"),
        ("2.0.0", ">1"),
        ("1.2.9", "~1.2"),
        ("0.9.0", "~0"),
        ("1.0.0", "<=1"),
        ("3.1.0", "1.x || >=3"),
        ("0.0.1", ""),
        ("1.2.3-rc.1", "1.2.3-rc.1"),
    ],
)
def test_satisfies_true(version, rng):
    assert satisfies(version, rng)


@pytest.mark.parametrize(
    "version,rng",
    [
        ("0.3.0", "^0.2.3"),
        ("0.0.4", "^0.0.3"),
        ("2.0.0-beta", "^1.2.3"),
        ("1.3.0-beta", "^1.2.3"),
        ("1.3.0-beta", "~1.2.3"),
        ("1.2.4-beta", "^1.2.3-beta.2"),
        ("3.4.5-alpha.9", ">1.2.3-alpha.3"),
        ("1.2.0", ">1.2"),
        ("1.2.9", ">1.2"),
        ("1.2.0-rc.1", ">=1.1.0"),
        ("2.4.0", "1.2.3 - 2.3"),
        ("2.4.0-0", "1.2.3 - 2.3"),
        ("1.0.0", "<1"),
        ("0.0.0", "<*"),
        ("not-a-version", "*"),
        ("1.2.3.4", "*"),
        ("1.0.0-rc.1", "1.x"),
    ],
)
def test_satisfies_false(version, rng):
    assert not satisfies(version, rng)


def test_include_prerelease():
    assert not satisfies("1.3.0-beta", "^1.2.3")
    assert satisfies("1.3.0-beta", "^1.2.3", include_prerelease=True)
    assert not satisfies("2.0.0-beta", "^1.2.3", include_prerelease=True)
    assert satisfies("1.0.0-rc.1", ">=0.9.0", include_prerelease=True)


def test_prerelease_rule_is_per_set():
    # The prerelease comparator must be in the same comparator set.
    assert not satisfies("1.2.4-beta", ">=1.2.4 || >=1.0.0-alpha.1")
    assert satisfies("1.2.4-beta", ">=1.2.4-alpha <2 || 3.x")


def test_version_objects_accepted():
    assert satisfies(parse_version("1.2.5"), "^1.2.3")


def test_max_min_satisfying():
    vs = ["1.2.3", "v1.4.0", "1.4.0-beta", "2.0.0", "junk", "1.3.9"]
    assert max_satisfying(vs, "^1.2") == "v1.4.0"
    assert min_satisfying(vs, "^1.2") == "1.2.3"
    assert max_satisfying(vs, "^1.2", include_prerelease=True) == "v1.4.0"
    assert max_satisfying(vs, ">=3") is None
    assert min_satisfying(vs, "<1.3.0-0 || >=1.4.0-alpha <1.5") == "1.2.3"
    assert max_satisfying(["1.4.0-beta", "1.3.0"], ">=1.4.0-alpha <1.5") == "1.4.0-beta"
    objs = [parse_version("0.1.0"), parse_version("0.1.5")]
    best = max_satisfying(objs, "^0.1")
    assert isinstance(best, Version) and str(best) == "0.1.5"
    assert max_satisfying(["1.2.3+a", "1.2.3+b"], "1.2.3") in ("1.2.3+a", "1.2.3+b")
