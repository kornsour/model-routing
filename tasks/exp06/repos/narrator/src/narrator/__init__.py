"""EPUB to M4B with local TTS."""

LEGACY_PRESETS = {
    "amber": "en_US-amy-medium",
    "slate": "en_US-ryan-high",
    "reed": "en_GB-alan-medium",
}


def resolve_voice(name: str) -> str:
    return LEGACY_PRESETS.get(name, name)
