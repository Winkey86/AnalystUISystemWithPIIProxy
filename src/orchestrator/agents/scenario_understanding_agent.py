"""Scenario understanding agent with narrow responsibility."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ScenarioUnderstandingResult:
    intent: str
    scenario_hints: list[str]
    attachment_artifact_needs: list[str]
    normalized_task_description: str


class ScenarioUnderstandingAgent:
    """Produces intent and scenario hints from user input."""

    def analyze(self, user_message: str, attachments: list[str] | None = None) -> ScenarioUnderstandingResult:
        normalized = " ".join(user_message.strip().split())
        hints: list[str] = []
        needs: list[str] = []

        lowered = normalized.lower()
        if attachments:
            hints.append("file_analysis")
            needs.append("attachment_present")
        if any(token in lowered for token in ("график", "документ", "картинка", "image", "chart")):
            hints.append("artifact_first_response")
            needs.append("artifact_requested")

        if not hints:
            hints.append("factual_qa")

        return ScenarioUnderstandingResult(
            intent="answer_user_request",
            scenario_hints=hints,
            attachment_artifact_needs=needs,
            normalized_task_description=normalized,
        )
