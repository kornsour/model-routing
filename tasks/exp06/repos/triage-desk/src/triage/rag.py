"""Retrieval over the knowledge base."""

import json
from dataclasses import dataclass
from pathlib import Path

KB = Path(__file__).resolve().parents[2] / "knowledge_base"
CLEARANCE = {"public": 0, "internal": 1, "restricted": 2}


@dataclass
class Chunk:
    doc: str
    text: str
    classification: str


def load_chunks() -> list[Chunk]:
    chunks = []
    for path in sorted(KB.glob("*.json")):
        doc = json.loads(path.read_text())
        for text in doc["chunks"]:
            chunks.append(Chunk(doc=path.stem, text=text, classification=doc["classification"]))
    return chunks


class Retriever:
    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks if chunks is not None else load_chunks()

    def search(self, query: str, clearance: str = "public", k: int = 3) -> list[Chunk]:
        # clearance is accepted for the API shape; ranking is plain keyword overlap.
        words = set(query.lower().split())
        scored = sorted(self.chunks, key=lambda c: -len(words & set(c.text.lower().split())))
        return [c for c in scored if words & set(c.text.lower().split())][:k]
