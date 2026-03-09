from orchestrator.scenarios.base import ScenarioSpec
from orchestrator.scenarios.registry import build_default_registry


def test_default_registry_contains_expected_scenarios() -> None:
    registry = build_default_registry()
    assert registry.list_ids() == ["artifact_first_response", "factual_qa", "file_analysis"]


def test_registered_scenario_has_required_contract_fields() -> None:
    registry = build_default_registry()
    spec = registry.get("factual_qa")

    assert isinstance(spec, ScenarioSpec)
    assert spec.id == "factual_qa"
    assert spec.description
    assert spec.required_evidence_slots
    assert spec.max_steps > 0
    assert spec.completion_rule
    assert spec.allowed_capability_tags
