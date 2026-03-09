"""Stop logic for orchestration flow."""

from __future__ import annotations

from typing import Any


class StopController:
    """Evaluates whether accumulated evidence is sufficient to stop."""

    def has_sufficient_evidence(self, evidence: list[dict[str, Any]]) -> bool:
        return len(evidence) >= 1

    def next_after_sufficiency(self, evidence: list[dict[str, Any]]) -> str:
        if self.has_sufficient_evidence(evidence):
            return "compose_response"
        return "select_capability"
