"""Runtime entrypoints for the orchestration graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict, cast


Role = Literal["user", "assistant", "system"]


class Message(TypedDict):
    role: Role
    content: str


@dataclass(slots=True)
class ResponsePackage:
    """Final response returned by the orchestration runtime."""

    text: str
    evidence_count: int
    scenario: str


class OrchestratorState(TypedDict, total=False):
    """Minimal state for running a deterministic orchestration pipeline."""

    messages: list[Message]
    attachments: list[str]
    active_scenario: str
    active_plan: list[str]
    selected_capability: str
    capability_result: dict[str, Any]
    validated_evidence: list[dict[str, Any]]
    summary_memory: list[str]
    working_memory: dict[str, Any]
    response_package: ResponsePackage
    persist_status: str


def make_initial_state(
    user_message: str,
    attachments: list[str] | None = None,
) -> OrchestratorState:
    return {
        "messages": [{"role": "user", "content": user_message}],
        "attachments": attachments or [],
        "validated_evidence": [],
        "summary_memory": [],
        "working_memory": {},
    }


def run_once(user_message: str, attachments: list[str] | None = None) -> OrchestratorState:
    from orchestrator.core.graph import build_graph

    graph = build_graph()
    initial_state = make_initial_state(user_message, attachments=attachments)
    return cast(OrchestratorState, graph.invoke(initial_state))
