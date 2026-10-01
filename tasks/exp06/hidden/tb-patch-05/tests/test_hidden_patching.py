import difflib

import pytest

from toolbelt.patching import PatchError, PatchResult, apply_patch


def udiff(a: str, b: str, n: int = 3) -> str:
    return "".join(
        difflib.unified_diff(a.splitlines(True), b.splitlines(True), "a/f", "b/f", n=n)
    )


BASE = "".join(f"line {i}\n" for i in range(1, 31))


def edited(text: str, **repl: str) -> str:
    lines = text.splitlines(True)
    for k, v in repl.items():
        idx = int(k[1:]) - 1
        lines[idx] = v
    return "".join(lines)


def test_simple_hunk():
    new = edited(BASE, l5="five\n")
    res = apply_patch(BASE, udiff(BASE, new))
    assert isinstance(res, PatchResult)
    assert res.text == new
    assert res.offsets == [0]


def test_multiple_hunks_and_insert_delete():
    lines = BASE.splitlines(True)
    new_lines = lines[:2] + ["inserted a\n", "inserted b\n"] + lines[2:14] + lines[16:25] + ["x\n"] + lines[25:]
    new = "".join(new_lines)
    patch = udiff(BASE, new, n=2)
    assert apply_patch(BASE, patch).text == new
    assert apply_patch(new, patch, reverse=True).text == BASE


def test_offset_when_lines_were_added_above():
    new = edited(BASE, l20="twenty\n")
    patch = udiff(BASE, new)
    drifted = "header 1\nheader 2\nheader 3\n" + BASE
    res = apply_patch(drifted, patch)
    assert res.text == "header 1\nheader 2\nheader 3\n" + new
    assert res.offsets == [3]


def test_offset_carries_to_later_hunks_and_is_per_hunk():
    new = edited(BASE, l4="four\n", l25="twentyfive\n")
    patch = udiff(BASE, new, n=1)
    lines = BASE.splitlines(True)
    drifted = "".join(lines[:10] + ["extra\n", "extra2\n"] + lines[10:])
    res = apply_patch(drifted, patch)
    assert res.offsets == [0, 2]
    exp = new.splitlines(True)
    assert res.text == "".join(exp[:10] + ["extra\n", "extra2\n"] + exp[10:])


def test_nearest_match_wins_and_ties_go_earlier():
    text = "a\nX\nb\nc\nX\nb\nd\ne\nX\nb\n"
    patch = "@@ -5,2 +5,2 @@\n X\n-b\n+B\n"
    assert apply_patch(text, patch).text == "a\nX\nb\nc\nX\nB\nd\ne\nX\nb\n"
    # expected at 0-based index 2; exact copies at 0 and 4 are equally far: the earlier wins
    text2 = "X\nb\nq\nq\nX\nb\n"
    patch2 = "@@ -3,2 +3,2 @@\n X\n-b\n+B\n"
    res = apply_patch(text2, patch2)
    assert res.text == "X\nB\nq\nq\nX\nb\n"
    assert res.offsets == [-2]


def test_hunks_do_not_reuse_consumed_lines():
    text = "k\nv\nk\nv\n"
    patch = "@@ -1,2 +1,2 @@\n k\n-v\n+V1\n@@ -3,2 +3,2 @@\n k\n-v\n+V2\n"
    assert apply_patch(text, patch).text == "k\nV1\nk\nV2\n"
    # the first hunk's offset carries: the second is then expected at index 1
    text2 = "h\nk\nv\nk\nv\n"
    patch2 = "@@ -3 +3 @@\n-h\n+H\n@@ -4,2 +4,2 @@\n k\n-v\n+V\n"
    res = apply_patch(text2, patch2)
    assert res.text == "H\nk\nV\nk\nv\n"
    assert res.offsets == [-2, -2]
    # the first hunk matched at the end; the only match for the second is before it
    text3 = "k\nv\nq\nq\nx\n"
    patch3 = "@@ -1 +1 @@\n-x\n+X\n@@ -2,2 +2,2 @@\n k\n-v\n+V\n"
    with pytest.raises(PatchError):
        apply_patch(text3, patch3)


def test_no_newline_at_end_markers():
    old = "a\nb\nc"
    new = "a\nb\nc\nd\n"
    patch = "--- a/f\n+++ b/f\n@@ -2,2 +2,3 @@\n b\n-c\n\\ No newline at end of file\n+c\n+d\n"
    assert apply_patch(old, patch).text == new
    assert apply_patch(new, patch, reverse=True).text == old
    patch2 = "@@ -1,3 +1,3 @@\n a\n b\n-c\n+z\n\\ No newline at end of file\n"
    assert apply_patch("a\nb\nc\n", patch2).text == "a\nb\nz"
    with pytest.raises(PatchError):
        apply_patch("a\nb\nc\n", patch)  # patch expects c without a newline


def test_difflib_no_newline_round_trip():
    a = "one\ntwo\nthree"
    b = "one\n2\nthree"
    patch = "@@ -1,3 +1,3 @@\n one\n-two\n+2\n three\n\\ No newline at end of file\n"
    assert apply_patch(a, patch).text == b


def test_pure_insertion_and_new_file():
    assert apply_patch("", "--- /dev/null\n+++ b/f\n@@ -0,0 +1,2 @@\n+x\n+y\n").text == "x\ny\n"
    assert apply_patch("a\nb\n", "@@ -1,0 +2 @@\n+mid\n").text == "a\nmid\nb\n"
    assert apply_patch("a\nb\n", "@@ -0,0 +1 @@\n+top\n").text == "top\na\nb\n"
    assert apply_patch("a\nb\n", "@@ -2,0 +3 @@\n+end\n").text == "a\nb\nend\n"


def test_whole_file_delete():
    assert apply_patch("x\ny\n", "@@ -1,2 +0,0 @@\n-x\n-y\n").text == ""


def test_counts_default_to_one_and_section_text_ignored():
    patch = "diff --git a/f b/f\nindex 1..2 100644\n--- a/f\n+++ b/f\n@@ -2 +2 @@ def section():\n-b\n+B\n"
    assert apply_patch("a\nb\nc\n", patch).text == "a\nB\nc\n"


def test_blank_context_line_without_space():
    patch = "@@ -1,3 +1,3 @@\n a\n\n-c\n+C\n"
    assert apply_patch("a\n\nc\n", patch).text == "a\n\nC\n"


@pytest.mark.parametrize(
    "text,patch",
    [
        ("a\nb\n", "@@ -1,2 +1,2 @@\n a\n-x\n+y\n"),
        ("a\nb\n", "no hunks here\n"),
        ("a\nb\n", "@@ -1,3 +1,2 @@\n a\n-b\n+c\n"),
        ("a\nb\n", "@@ -1,2 +1,3 @@\n a\n-b\n+c\n"),
        ("a\nb\n", "@@ garbage @@\n a\n"),
        ("a\nb\n", "@@ -1,2 +1,2 @@\n a\n*b\n+c\n"),
        ("a\nb\nc\nd\n", "@@ -3,1 +3,1 @@\n-c\n+C\n@@ -1,1 +1,1 @@\n-a\n+A\n"),
        ("a\nb\n", "@@ -5,0 +6 @@\n+z\n"),
        ("a\nb\n", "@@ -1 +1 @@\n-a\n+A\n--- a/g\n+++ b/g\n@@ -1 +1 @@\n-x\n+y\n"),
    ],
)
def test_errors(text, patch):
    with pytest.raises(PatchError):
        apply_patch(text, patch)


def test_error_is_value_error_and_input_untouched():
    assert issubclass(PatchError, ValueError)
    text = "a\nb\nc\n"
    patch = "@@ -1 +1 @@\n-a\n+A\n@@ -3 +3 @@\n-zzz\n+C\n"
    with pytest.raises(PatchError, match="2"):
        apply_patch(text, patch)


@pytest.mark.parametrize("seed", range(12))
def test_random_round_trips(seed):
    import random

    rng = random.Random(seed)
    a_lines = [f"w{rng.randrange(8)}\n" for _ in range(rng.randrange(5, 60))]
    b_lines = list(a_lines)
    for _ in range(rng.randrange(1, 8)):
        op = rng.choice(["ins", "del", "mod"])
        i = rng.randrange(len(b_lines) + (op == "ins"))
        if op == "ins":
            b_lines.insert(i, f"new{rng.randrange(100)}\n")
        elif op == "del" and b_lines:
            del b_lines[min(i, len(b_lines) - 1)]
        elif b_lines:
            b_lines[min(i, len(b_lines) - 1)] = f"mod{rng.randrange(100)}\n"
    a, b = "".join(a_lines), "".join(b_lines)
    patch = udiff(a, b, n=rng.choice([0, 1, 3]))
    if not patch:
        return
    assert apply_patch(a, patch).text == b
    assert apply_patch(b, patch, reverse=True).text == a
