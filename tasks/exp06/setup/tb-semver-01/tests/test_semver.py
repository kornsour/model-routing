from toolbelt.semver import max_satisfying, parse_version, satisfies


def test_parse_and_order():
    assert parse_version("1.2.3") < parse_version("1.10.0")
    assert parse_version("1.0.0-rc.1") < parse_version("1.0.0")


def test_simple_ranges():
    assert satisfies("1.2.5", "^1.2.3")
    assert not satisfies("2.0.0", "^1.2.3")
    assert satisfies("1.2.9", "~1.2.3")
    assert not satisfies("1.3.0", "~1.2.3")
    assert satisfies("1.4.0", ">=1.2.0 <2.0.0")
    assert satisfies("3.0.0", "1.x || >=3")


def test_max_satisfying():
    assert max_satisfying(["1.2.3", "1.4.0", "2.0.0"], "^1.2") == "1.4.0"
