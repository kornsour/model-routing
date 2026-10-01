import copy

import pytest

from toolbelt.jsonpatch import PatchError, apply_patch, diff, make_pointer, resolve

RFC_DOC = {
    "foo": ["bar", "baz"],
    "": 0,
    "a/b": 1,
    "c%d": 2,
    "e^f": 3,
    "g|h": 4,
    "i\\j": 5,
    'k"l': 6,
    " ": 7,
    "m~n": 8,
}


@pytest.mark.parametrize(
    "ptr,expected",
    [
        ("", RFC_DOC),
        ("/foo", ["bar", "baz"]),
        ("/foo/0", "bar"),
        ("/", 0),
        ("/a~1b", 1),
        ("/c%d", 2),
        ("/e^f", 3),
        ("/g|h", 4),
        ("/i\\j", 5),
        ('/k"l', 6),
        ("/ ", 7),
        ("/m~0n", 8),
    ],
)
def test_rfc6901_examples(ptr, expected):
    assert resolve(RFC_DOC, ptr) == expected


def test_escape_order():
    assert resolve({"~1": "tilde-one", "/": "slash"}, "/~01") == "tilde-one"
    assert make_pointer(["~1", "a/b", 3]) == "/~01/a~1b/3"
    assert make_pointer([]) == ""


@pytest.mark.parametrize("ptr", ["foo", "/foo/2", "/foo/01", "/foo/-", "/nope", "/foo/0/x", "/m~2n", "/foo/-1"])
def test_resolve_errors(ptr):
    with pytest.raises(PatchError):
        resolve(RFC_DOC, ptr)


def test_patch_error_is_value_error():
    assert issubclass(PatchError, ValueError)


@pytest.mark.parametrize(
    "doc,patch,expected",
    [
        ({"foo": "bar"}, [{"op": "add", "path": "/baz", "value": "qux"}], {"foo": "bar", "baz": "qux"}),
        ({"foo": ["bar", "baz"]}, [{"op": "add", "path": "/foo/1", "value": "qux"}], {"foo": ["bar", "qux", "baz"]}),
        ({"foo": ["bar"]}, [{"op": "add", "path": "/foo/-", "value": "x"}], {"foo": ["bar", "x"]}),
        ({"foo": ["bar"]}, [{"op": "add", "path": "/foo/1", "value": "x"}], {"foo": ["bar", "x"]}),
        ({"baz": "qux", "foo": "bar"}, [{"op": "remove", "path": "/baz"}], {"foo": "bar"}),
        ({"foo": ["bar", "qux", "baz"]}, [{"op": "remove", "path": "/foo/1"}], {"foo": ["bar", "baz"]}),
        ({"baz": "qux", "foo": "bar"}, [{"op": "replace", "path": "/baz", "value": "boo"}], {"baz": "boo", "foo": "bar"}),
        (
            {"foo": {"bar": "baz", "waldo": "fred"}, "qux": {"corge": "grault"}},
            [{"op": "move", "from": "/foo/waldo", "path": "/qux/thud"}],
            {"foo": {"bar": "baz"}, "qux": {"corge": "grault", "thud": "fred"}},
        ),
        ({"foo": ["all", "grass", "cows", "eat"]}, [{"op": "move", "from": "/foo/1", "path": "/foo/3"}], {"foo": ["all", "cows", "eat", "grass"]}),
        ({"foo": "bar"}, [{"op": "add", "path": "/child", "value": {"grandchild": {}}}], {"foo": "bar", "child": {"grandchild": {}}}),
        ({"foo": "bar"}, [{"op": "add", "path": "/baz", "value": "qux", "xyz": 123}], {"foo": "bar", "baz": "qux"}),
        ({"foo": ["bar", "baz"]}, [{"op": "add", "path": "/foo/-", "value": ["abc", "def"]}], {"foo": ["bar", "baz", ["abc", "def"]]}),
        ({"foo": 1}, [{"op": "add", "path": "", "value": [1, 2]}], [1, 2]),
        ({"foo": 1}, [{"op": "replace", "path": "", "value": {"x": 1}}], {"x": 1}),
        ({"a": {"b": 1}}, [{"op": "copy", "from": "/a", "path": "/c"}], {"a": {"b": 1}, "c": {"b": 1}}),
        ({"a": 1}, [{"op": "move", "from": "/a", "path": "/a"}], {"a": 1}),
        ({"a": 1}, [{"op": "add", "path": "/a", "value": 2}], {"a": 2}),
        ({"": 1}, [{"op": "replace", "path": "/", "value": 2}], {"": 2}),
        ([1, 2, 3], [{"op": "move", "from": "/0", "path": "/-"}], [2, 3, 1]),
    ],
)
def test_rfc6902_ops(doc, patch, expected):
    assert apply_patch(doc, patch) == expected


@pytest.mark.parametrize(
    "doc,patch",
    [
        ({"foo": "bar"}, [{"op": "add", "path": "/baz/bat", "value": "qux"}]),
        ({"foo": ["bar"]}, [{"op": "add", "path": "/foo/2", "value": "x"}]),
        ({"foo": ["bar"]}, [{"op": "add", "path": "/foo/01", "value": "x"}]),
        ({"foo": ["bar"]}, [{"op": "remove", "path": "/foo/1"}]),
        ({"foo": ["bar"]}, [{"op": "remove", "path": "/foo/-"}]),
        ({"foo": ["bar"]}, [{"op": "replace", "path": "/foo/-", "value": 1}]),
        ({"foo": "bar"}, [{"op": "remove", "path": "/baz"}]),
        ({"foo": "bar"}, [{"op": "replace", "path": "/baz", "value": 1}]),
        ({"foo": "bar"}, [{"op": "move", "from": "/baz", "path": "/x"}]),
        ({"foo": "bar"}, [{"op": "copy", "from": "/baz", "path": "/x"}]),
        ({"a": {"b": 1}}, [{"op": "move", "from": "/a", "path": "/a/b/c"}]),
        ({"foo": "bar"}, [{"op": "frob", "path": "/foo"}]),
        ({"foo": "bar"}, [{"path": "/foo", "value": 1}]),
        ({"foo": "bar"}, [{"op": "add", "value": 1}]),
        ({"foo": "bar"}, [{"op": "add", "path": "/x"}]),
        ({"foo": "bar"}, [{"op": "replace", "path": "/foo"}]),
        ({"foo": "bar"}, [{"op": "test", "path": "/foo"}]),
        ({"foo": "bar"}, [{"op": "move", "path": "/x"}]),
        ({"foo": "bar"}, [{"op": "add", "path": "foo", "value": 1}]),
        ({"foo": "bar"}, [{"op": "add", "path": "/foo/x", "value": 1}]),
        ({"foo": "bar"}, [{"op": "remove", "path": ""}]),
        ({"foo": "bar"}, [{"op": "test", "path": "/foo", "value": "baz"}]),
        ({"n": 1}, [{"op": "test", "path": "/n", "value": True}]),
        ({"n": True}, [{"op": "test", "path": "/n", "value": 1}]),
        ({"n": [1, 2]}, [{"op": "test", "path": "/n", "value": [2, 1]}]),
        ({"n": "1"}, [{"op": "test", "path": "/n", "value": 1}]),
        ({"n": None}, [{"op": "test", "path": "/n", "value": False}]),
        ({"foo": "bar"}, {"op": "add", "path": "/x", "value": 1}),
    ],
)
def test_errors(doc, patch):
    before = copy.deepcopy(doc)
    with pytest.raises(PatchError):
        apply_patch(doc, patch)
    assert doc == before


def test_test_op_semantics():
    doc = {"baz": "qux", "foo": ["a", 2, "c"], "n": 10, "o": {"x": 1, "y": [1, {"z": None}]}}
    ok = [
        {"op": "test", "path": "/baz", "value": "qux"},
        {"op": "test", "path": "/foo/1", "value": 2},
        {"op": "test", "path": "/n", "value": 10.0},
        {"op": "test", "path": "/o", "value": {"y": [1.0, {"z": None}], "x": 1}},
        {"op": "test", "path": "", "value": copy.deepcopy(doc)},
    ]
    assert apply_patch(doc, ok) == doc


def test_atomic_and_no_mutation():
    doc = {"a": [1, 2], "b": {"c": 1}}
    before = copy.deepcopy(doc)
    patch = [
        {"op": "add", "path": "/a/-", "value": 3},
        {"op": "remove", "path": "/b/c"},
        {"op": "test", "path": "/a/2", "value": 99},
    ]
    with pytest.raises(PatchError):
        apply_patch(doc, patch)
    assert doc == before
    out = apply_patch(doc, patch[:2])
    assert out == {"a": [1, 2, 3], "b": {}}
    assert doc == before


def test_values_are_copied():
    value = {"deep": [1]}
    out = apply_patch({}, [{"op": "add", "path": "/v", "value": value}])
    value["deep"].append(2)
    assert out == {"v": {"deep": [1]}}
    out2 = apply_patch({"a": {"x": [1]}}, [{"op": "copy", "from": "/a", "path": "/b"}])
    out2["a"]["x"].append(9)
    assert out2["b"] == {"x": [1]}


def test_ops_see_earlier_ops():
    doc = {"list": []}
    patch = [
        {"op": "add", "path": "/list/-", "value": "a"},
        {"op": "add", "path": "/list/0", "value": "b"},
        {"op": "copy", "from": "/list/1", "path": "/first"},
        {"op": "move", "from": "/list", "path": "/moved"},
        {"op": "test", "path": "/moved", "value": ["b", "a"]},
    ]
    assert apply_patch(doc, patch) == {"first": "a", "moved": ["b", "a"]}


def test_diff_spec():
    a = {"x": {"y": 1, "z": 2}, "keep": [1, 2, 3], "gone": True, "n": 1}
    b = {"x": {"y": 5, "z": 2}, "keep": [1, 2, 3], "new": None, "n": 1.0}
    assert diff(a, b) == [
        {"op": "remove", "path": "/gone"},
        {"op": "add", "path": "/new", "value": None},
        {"op": "replace", "path": "/x/y", "value": 5},
    ]
    assert diff(a, a) == []
    assert diff([1, 2], [1, 3]) == [{"op": "replace", "path": "/1", "value": 3}]
    assert diff([1, 2], [1, 2, 3]) == [{"op": "replace", "path": "", "value": [1, 2, 3]}]
    assert diff({"t": 1}, {"t": True}) == [{"op": "replace", "path": "/t", "value": True}]
    assert diff({"a/b": {"m~n": 1}}, {"a/b": {"m~n": 2}}) == [
        {"op": "replace", "path": "/a~1b/m~0n", "value": 2}
    ]
    assert diff(1, "1") == [{"op": "replace", "path": "", "value": "1"}]


@pytest.mark.parametrize(
    "a,b",
    [
        ({"a": [1, {"b": 2}], "c": "d"}, {"a": [1, {"b": 3, "e": []}], "f": {"g": [None]}}),
        ([{"x": 1}, 2], [{"x": 1, "y": 2}, 3]),
        ({"k": {"deep": {"er": [1, 2]}}}, {"k": {"deep": {"er": [2, 1]}}}),
        ({}, {"~": {"/": 1}}),
    ],
)
def test_diff_round_trip(a, b):
    patch = diff(a, b)
    assert apply_patch(a, patch) == b
    b_copy = copy.deepcopy(b)
    patch[0]["value"] = "mutated" if "value" in patch[0] else None
    assert b == b_copy
