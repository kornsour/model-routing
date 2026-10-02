"""Model access. With no API key, a deterministic local model answers."""

import os


class LocalModel:
    def complete(self, prompt: str) -> str:
        first = prompt.strip().splitlines()[0] if prompt.strip() else ""
        return f"[local] Suggested reply based on: {first[:80]}"


class RemoteModel:  # pragma: no cover - needs a key and the network
    def __init__(self, key: str):
        self.key = key

    def complete(self, prompt: str) -> str:
        raise RuntimeError("network model not available in this build")


def get_model():
    key = os.environ.get("TRIAGE_API_KEY")
    return RemoteModel(key) if key else LocalModel()
