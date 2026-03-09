"""Context compression and response assembly agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class ContextAnswerResult:
    compressed_context: str
    artifact_package: list[dict[str, Any]]
    response_assembly: str


class ContextAnswerAgent:
    """Builds compact context and text response from evidence."""

    def assemble(self, scenario_id: str, validated_evidence: list[dict[str, Any]]) -> ContextAnswerResult:
        evidence_count = len(validated_evidence)
        compressed_context = f"scenario={scenario_id};validated_evidence={evidence_count}"
        artifact_package = [
            {
                "kind": "evidence_preview",
                "items": evidence_count,
            }
        ]
        response = f"Prepared response for '{scenario_id}' with {evidence_count} evidence item(s)."
        return ContextAnswerResult(
            compressed_context=compressed_context,
            artifact_package=artifact_package,
            response_assembly=response,
        )
