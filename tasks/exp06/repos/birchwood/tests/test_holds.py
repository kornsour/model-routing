from birchwood import hold_expired


def test_hold_expiry_boundary():
    assert not hold_expired(14.9)
    assert hold_expired(15)
