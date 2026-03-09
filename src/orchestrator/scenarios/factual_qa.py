"""Built-in scenario for plain factual Q&A."""

from orchestrator.scenarios.base import ScenarioSpec

SCENARIO = ScenarioSpec(
    id="factual_qa",
    description="General factual question answering without mandatory artifacts.",
    required_evidence_slots=["fact_answer"],
    optional_evidence_slots=["citations", "confidence_note"],
    max_steps=4,
    completion_rule="min_validated_evidence:1",
    allowed_capability_tags=["qa", "retrieval", "tool"],
)
