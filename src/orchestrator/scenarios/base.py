"""Base contracts for orchestration scenarios."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ScenarioSpec:
    """Declarative scenario specification used by planner and runtime."""

    id: str
    description: str
    required_evidence_slots: list[str]
    optional_evidence_slots: list[str]
    max_steps: int
    completion_rule: str
    allowed_capability_tags: list[str]

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("scenario id must be non-empty")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be > 0")
