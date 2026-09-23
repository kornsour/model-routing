"""Dispatch runner.  STUB - owned by the runner/policies workstream.  See ``api``."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from model_routing.dispatch.types import Progress
from model_routing.types import Candidate


@dataclass
class DispatchConfig:
    name: str
    tasks: Path
    candidates: dict[str, Candidate]
    policies: list[dict[str, Any]]
    parent: str
    menu: list[str]
    trials: int = 1
    order: str = "by_policy"
    hypothesis: str = ""
    primary: dict[str, str] = field(default_factory=lambda: {"treatment": "C1", "control": "B"})
    margin_pp: float = 5.0
    max_budget_per_session_usd: float = 2.0
    source: Path | None = None


def load_dispatch_config(path: str | Path) -> DispatchConfig:
    raise NotImplementedError


def estimate_dispatch(
    cfg: DispatchConfig,
    *,
    sample: int | None = None,
    trials: int | None = None,
    policies: list[str] | None = None,
) -> dict[str, Any]:
    raise NotImplementedError


def run_dispatch(
    cfg: DispatchConfig,
    *,
    out_dir: Path,
    budget_usd: float,
    sample: int | None = None,
    trials: int | None = None,
    policies: list[str] | None = None,
    fake: bool = False,
    progress: Callable[[Progress], None] | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    raise NotImplementedError


def auth_status() -> dict[str, dict[str, Any]]:
    raise NotImplementedError
