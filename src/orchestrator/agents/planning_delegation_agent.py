"""Planning and delegation agent with narrow responsibility."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class PlanningDelegationResult:
    next_step: str
    capability_type: str
    delegation_decision: str
    routing_hint: str


class PlanningDelegationAgent:
    """Suggests next planning action and routing mode."""

    def propose(self, scenario_id: str) -> PlanningDelegationResult:
        if scenario_id == "file_analysis":
            return PlanningDelegationResult(
                next_step="select_capability",
                capability_type="file_tool",
                delegation_decision="delegate_to_tool",
                routing_hint="tool:file_pipeline",
            )

        if scenario_id == "artifact_first_response":
            return PlanningDelegationResult(
                next_step="select_capability",
                capability_type="artifact_tool",
                delegation_decision="delegate_to_workflow",
                routing_hint="workflow:artifact_generation",
            )

        return PlanningDelegationResult(
            next_step="select_capability",
            capability_type="qa_tool",
            delegation_decision="delegate_to_tool",
            routing_hint="tool:qa",
        )
