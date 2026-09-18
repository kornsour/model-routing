"""List-price cost computation from token usage."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from model_routing.types import Usage


@dataclass(frozen=True)
class Price:
    model: str
    input: float
    cache_read: float
    cache_write: float
    output: float
    cache_write_1h: float | None = None
    verified: bool = True

    def cost(self, u: Usage) -> float:
        per = 1_000_000
        write_1h = self.cache_write_1h if self.cache_write_1h is not None else self.cache_write
        write_5m = max(u.cache_write - u.cache_write_1h, 0)
        return (
            u.input_tokens * self.input
            + u.cache_read * self.cache_read
            + write_5m * self.cache_write
            + u.cache_write_1h * write_1h
            + u.output_tokens * self.output
        ) / per


class PriceTable:
    def __init__(self, rows: dict[str, Price]):
        self._rows = rows

    @classmethod
    def load(cls, path: str | Path | None = None) -> PriceTable:
        if path is None:
            text = resources.files("model_routing").joinpath("data/pricing.toml").read_text()
        else:
            text = Path(path).read_text()
        data = tomllib.loads(text)
        rows: dict[str, Price] = {}
        for _vendor, models in data.items():
            for model, spec in models.items():
                price = Price(
                    model=model,
                    input=float(spec["input"]),
                    cache_read=float(spec.get("cache_read", spec["input"])),
                    cache_write=float(spec.get("cache_write", spec["input"])),
                    output=float(spec["output"]),
                    cache_write_1h=(
                        float(spec["cache_write_1h"]) if "cache_write_1h" in spec else None
                    ),
                    verified=bool(spec.get("verified", True)),
                )
                rows[model] = price
                for alias in spec.get("aliases", []):
                    rows[alias] = price
        return cls(rows)

    def get(self, model: str) -> Price | None:
        return self._rows.get(model)

    def cost(self, model: str, usage: Usage) -> float:
        """Cost at list price; ``ValueError`` when the model has no row."""
        price = self.get(model)
        if price is None:
            raise ValueError(
                f"no price row for model {model!r}; add it to src/model_routing/data/pricing.toml"
            )
        return price.cost(usage)

    def models(self) -> list[str]:
        return sorted({p.model for p in self._rows.values()})
