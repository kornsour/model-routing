from invoicing.formatting import format_money


def test_negative_amount_sign_before_dollar():
    assert format_money(-5.0) == "-$5.00"


def test_zero_is_not_negative():
    assert format_money(0.0) == "$0.00"
