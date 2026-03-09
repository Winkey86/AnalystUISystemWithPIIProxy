"""Built-in scenario for requests that include files/attachments."""

from orchestrator.scenarios.base import ScenarioSpec

SCENARIO = ScenarioSpec(
    id="file_analysis",
    description="Analyze attached files and produce structured findings.",
    required_evidence_slots=["file_summary"],
    optional_evidence_slots=["schema", "quality_findings", "transform_preview"],
    max_steps=6,
    completion_rule="min_validated_evidence:1",
    allowed_capability_tags=["file", "analysis", "tool"],
)
