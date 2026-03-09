"""Scenario registry for lookup and extension."""

from __future__ import annotations

from orchestrator.scenarios.artifact_first_response import SCENARIO as ARTIFACT_FIRST_RESPONSE
from orchestrator.scenarios.base import ScenarioSpec
from orchestrator.scenarios.factual_qa import SCENARIO as FACTUAL_QA
from orchestrator.scenarios.file_analysis import SCENARIO as FILE_ANALYSIS


class ScenarioRegistry:
    """In-memory registry of scenario specifications."""

    def __init__(self) -> None:
        self._scenarios: dict[str, ScenarioSpec] = {}

    def register(self, spec: ScenarioSpec) -> None:
        self._scenarios[spec.id] = spec

    def get(self, scenario_id: str) -> ScenarioSpec:
        return self._scenarios[scenario_id]

    def list_ids(self) -> list[str]:
        return sorted(self._scenarios.keys())

    def all(self) -> list[ScenarioSpec]:
        return [self._scenarios[key] for key in self.list_ids()]


def build_default_registry() -> ScenarioRegistry:
    registry = ScenarioRegistry()
    registry.register(FACTUAL_QA)
    registry.register(FILE_ANALYSIS)
    registry.register(ARTIFACT_FIRST_RESPONSE)
    return registry
