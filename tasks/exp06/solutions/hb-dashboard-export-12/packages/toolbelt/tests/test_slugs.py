from toolbelt.text import unique_slugs


def test_collisions_get_suffixes():
    assert unique_slugs(["A b", "a-b"]) == {"A b": "a-b", "a-b": "a-b-2"}
