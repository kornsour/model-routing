from invoicing.calc import round_currency


def test_round_currency_half_up_at_boundary():
    # 0.125 is exactly representable in binary; banker's rounding would give
    # 0.12 (12 is even), but an invoice should round half-up to 0.13.
    assert round_currency(0.125) == 0.13
