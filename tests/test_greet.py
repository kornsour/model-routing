from python_template import greet


def test_greet_returns_greeting():
    assert greet("world") == "Hello, world!"


def test_greet_uses_the_name():
    assert "Ada" in greet("Ada")
