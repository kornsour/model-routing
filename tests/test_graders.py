from model_routing.graders import grade


def test_exact_is_normalized():
    assert grade({"type": "exact", "value": "Negative"}, "  negative. ")[0]
    assert not grade({"type": "exact", "value": "negative"}, "positive")[0]


def test_number_first_number_with_commas():
    ok, _ = grade({"type": "number", "value": 3145, "tol": 0}, "Total: 3,145 units")
    assert ok
    assert not grade({"type": "number", "value": 1, "tol": 0}, "no digits here")[0]


def test_number_grader_prefers_final_answer_over_restated_inputs():
    verbose = (
        "A = P(1 + r/n)^(nt)\nWhere P = $10,000, r = 0.06, n = 12, t = 5\n"
        "A = 10000 x 1.34885 = 13488.50\n\nRounded to the nearest cent: **13488.50**"
    )
    assert grade({"type": "number", "value": 13488.5, "tol": 0.1}, verbose)[0]
    wrong = verbose.replace("13488.50", "13498.59")
    ok, detail = grade({"type": "number", "value": 13488.5, "tol": 0.1}, wrong)
    assert not ok and "13498.59" in detail


def test_json_fields_tolerates_fences_and_prose():
    spec = {"type": "json_fields", "expect": {"client": "Acme", "budget_usd": 48000}}
    out = 'Sure!\n```json\n{"client": "acme", "budget_usd": 48000.0}\n```'
    assert grade(spec, out)[0]
    assert grade(spec, "", structured={"client": "Acme", "budget_usd": 48000})[0]
    assert not grade(spec, '{"client": "Acme", "budget_usd": 1}')[0]


def test_all_of_short_circuits_with_detail():
    spec = {
        "type": "all_of",
        "graders": [
            {"type": "contains_all", "values": ["thursday"]},
            {"type": "max_words", "value": 3},
        ],
    }
    ok, detail = grade(spec, "late until Thursday, sorry about that")
    assert not ok and "max_words" in detail


def test_regex_and_unknown():
    assert grade({"type": "regex", "pattern": r"12:00\s*PM\s*ET"}, "Earliest: 12:00 PM ET.")[0]
    assert not grade({"type": "bogus"}, "x")[0]
