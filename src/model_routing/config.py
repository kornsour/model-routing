"""Experiment config (TOML) -> typed objects.  See experiments/llm/*.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from model_routing.auth import AuthConfig, parse_auth
from model_routing.types import Candidate


@dataclass
class ExperimentConfig:
    name: str
    tasks: Path
    candidates: dict[str, Candidate]
    routers: list[dict[str, Any]]
    trials: int = 1
    order: str = "fixed"  # fixed | shuffle | by_router  (see runner)
    hypothesis: str = ""
    limit: int | None = None
    tags: tuple[str, ...] = ()
    provider_options: dict[str, dict[str, Any]] = field(default_factory=dict)
    auth: dict[str, AuthConfig] = field(default_factory=lambda: {"*": AuthConfig()})
    source: Path | None = None

    def auth_for(self, provider: str) -> AuthConfig:
        return self.auth.get(provider, self.auth["*"])

    def validate(self) -> None:
        for r in self.routers:
            for key in ("candidate", "classifier"):
                if key in r and r[key] not in self.candidates:
                    raise ValueError(f"router {r['name']!r}: unknown {key} {r[key]!r}")
            for c in r.get("chain", []):
                if c not in self.candidates:
                    raise ValueError(f"router {r['name']!r}: unknown chain member {c!r}")
            for c in r.get("map", {}).values():
                if c not in self.candidates:
                    raise ValueError(f"router {r['name']!r}: unknown map target {c!r}")
        names = [r["name"] for r in self.routers]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate router names: {names}")


def load_config(path: str | Path) -> ExperimentConfig:
    path = Path(path)
    data = tomllib.loads(path.read_text())
    exp = data["experiment"]
    candidates = {
        name: Candidate(
            name=name,
            provider=spec["provider"],
            model=spec["model"],
            effort=spec.get("effort"),
            extra={k: v for k, v in spec.items() if k not in ("provider", "model", "effort")},
        )
        for name, spec in data.get("candidates", {}).items()
    }
    tasks_path = Path(exp["tasks"])
    if not tasks_path.is_absolute():
        # Relative to the repo root (the directory containing experiments/).
        root = next(
            (p for p in path.resolve().parents if (p / "pyproject.toml").exists()), Path.cwd()
        )
        tasks_path = root / tasks_path
    cfg = ExperimentConfig(
        name=exp["name"],
        tasks=tasks_path,
        candidates=candidates,
        routers=list(data.get("routers", [])),
        trials=int(exp.get("trials", 1)),
        order=str(exp.get("order", "fixed")),
        hypothesis=str(exp.get("hypothesis", "")),
        limit=exp.get("limit"),
        tags=tuple(exp.get("tags", ())),
        provider_options=dict(data.get("providers", {})),
        auth=parse_auth(data.get("auth", {})),
        source=path,
    )
    cfg.validate()
    return cfg
