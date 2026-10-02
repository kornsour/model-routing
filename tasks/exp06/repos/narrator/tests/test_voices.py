from narrator import resolve_voice


def test_legacy_presets_still_resolve():
    assert resolve_voice("amber") == "en_US-amy-medium"
    assert resolve_voice("en_US-lessac-high") == "en_US-lessac-high"
