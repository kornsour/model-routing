"""Agentic task loader.  STUB - owned by the task-set workstream."""

from __future__ import annotations

from pathlib import Path

from model_routing.dispatch.types import AgentTask


def load_agent_tasks(path: Path, *, sample: int | None = None, seed: int = 0) -> list[AgentTask]:
    """Load ``tasks/agentic/tasks.jsonl``; resolve ``repo`` and hidden-test paths
    relative to the JSONL's directory.  ``sample`` draws a deterministic,
    difficulty-stratified subset."""
    raise NotImplementedError
