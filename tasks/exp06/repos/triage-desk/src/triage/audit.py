"""Append-only audit log, hash-chained."""

import hashlib
import json
from dataclasses import dataclass, field

GENESIS = "0" * 64


def _digest(prev: str, event: dict) -> str:
    body = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev + body).encode()).hexdigest()


@dataclass
class AuditLog:
    entries: list[dict] = field(default_factory=list)

    def append(self, event: dict) -> str:
        prev = self.entries[-1]["hash"] if self.entries else GENESIS
        digest = _digest(prev, event)
        self.entries.append({"event": event, "prev": prev, "hash": digest})
        return digest

    def verify_chain(self) -> bool:
        prev = GENESIS
        for entry in self.entries:
            if entry["prev"] != prev or _digest(prev, entry["event"]) != entry["hash"]:
                return False
            prev = entry["hash"]
        return True
