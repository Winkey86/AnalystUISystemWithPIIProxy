"""Built-in scenario for artifact-first responses (charts/docs/images)."""

from orchestrator.scenarios.base import ScenarioSpec

SCENARIO = ScenarioSpec(
    id="artifact_first_response",
    description="Generate or present artifact-centric output before prose answer.",
    required_evidence_slots=["artifact_ref"],
    optional_evidence_slots=["artifact_caption", "render_hint"],
    max_steps=5,
    completion_rule="min_validated_evidence:1",
    allowed_capability_tags=["artifact", "visualization", "document"],
)
