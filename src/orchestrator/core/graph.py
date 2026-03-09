"""StateGraph definition and node handlers for orchestration runtime."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from orchestrator.planner.scenario_resolver import resolve_scenario_id
from orchestrator.planner.stop_controller import StopController
from orchestrator.scenarios.registry import build_default_registry


def load_state(state: dict[str, Any]) -> dict[str, Any]:
    # Ensure mutable containers exist even if partial state is provided.
    return {
        "validated_evidence": state.get("validated_evidence", []),
        "summary_memory": state.get("summary_memory", []),
        "working_memory": state.get("working_memory", {}),
    }


def resolve_scenario(state: dict[str, Any]) -> dict[str, Any]:
    messages = state.get("messages", [])
    user_message = messages[-1]["content"] if messages else ""
    attachments = state.get("attachments", [])

    scenario_id = resolve_scenario_id(user_message=user_message, attachments=attachments)
    registry = build_default_registry()
    if scenario_id not in registry.list_ids():
        raise ValueError(f"Unknown scenario resolved: {scenario_id}")
    return {"active_scenario": scenario_id}


def build_plan(_: dict[str, Any]) -> dict[str, Any]:
    return {
        "active_plan": [
            "select_capability",
            "execute_capability",
            "validate_result",
            "summarize_context",
            "update_memory",
            "evaluate_sufficiency",
        ]
    }


def select_capability(_: dict[str, Any]) -> dict[str, Any]:
    return {"selected_capability": "stub_capability"}


def execute_capability(state: dict[str, Any]) -> dict[str, Any]:
    user_messages = state.get("messages", [])
    last_message = user_messages[-1]["content"] if user_messages else ""
    result = {
        "capability": state.get("selected_capability", "stub_capability"),
        "payload": f"stub-result-for:{last_message}",
        "status": "ok",
    }
    return {"capability_result": result}


def validate_result(state: dict[str, Any]) -> dict[str, Any]:
    current = list(state.get("validated_evidence", []))
    capability_result = state.get("capability_result", {})
    if capability_result.get("status") == "ok":
        current.append(
            {
                "type": "capability_output",
                "value": capability_result.get("payload", ""),
                "source": capability_result.get("capability", "unknown"),
                "validated": True,
            }
        )
    return {"validated_evidence": current}


def summarize_context(state: dict[str, Any]) -> dict[str, Any]:
    evidence = state.get("validated_evidence", [])
    summary = f"validated_evidence={len(evidence)}"
    memories = list(state.get("summary_memory", []))
    memories.append(summary)
    return {"summary_memory": memories}


def update_memory(state: dict[str, Any]) -> dict[str, Any]:
    working_memory = dict(state.get("working_memory", {}))
    working_memory["last_summary"] = state.get("summary_memory", [""])[-1]
    working_memory["evidence_count"] = len(state.get("validated_evidence", []))
    return {"working_memory": working_memory}


def evaluate_sufficiency(state: dict[str, Any]) -> dict[str, Any]:
    # Node is intentionally lightweight; routing is handled by conditional edge.
    evidence_count = len(state.get("validated_evidence", []))
    return {"working_memory": {**state.get("working_memory", {}), "sufficient": evidence_count >= 1}}


def route_after_sufficiency(state: dict[str, Any]) -> str:
    controller = StopController()
    evidence = state.get("validated_evidence", [])
    return controller.next_after_sufficiency(evidence)


def compose_response(state: dict[str, Any]) -> dict[str, Any]:
    from orchestrator.core.runtime import ResponsePackage

    evidence = state.get("validated_evidence", [])
    scenario = state.get("active_scenario", "unknown")
    text = f"Scenario '{scenario}' completed with {len(evidence)} validated evidence item(s)."
    return {
        "response_package": ResponsePackage(
            text=text,
            evidence_count=len(evidence),
            scenario=scenario,
        )
    }


def persist_run(_: dict[str, Any]) -> dict[str, Any]:
    return {"persist_status": "stored"}


def build_graph() -> Any:
    from orchestrator.core.runtime import OrchestratorState

    graph = StateGraph(OrchestratorState)

    graph.add_node("load_state", load_state)
    graph.add_node("resolve_scenario", resolve_scenario)
    graph.add_node("build_plan", build_plan)
    graph.add_node("select_capability", select_capability)
    graph.add_node("execute_capability", execute_capability)
    graph.add_node("validate_result", validate_result)
    graph.add_node("summarize_context", summarize_context)
    graph.add_node("update_memory", update_memory)
    graph.add_node("evaluate_sufficiency", evaluate_sufficiency)
    graph.add_node("compose_response", compose_response)
    graph.add_node("persist_run", persist_run)

    graph.add_edge(START, "load_state")
    graph.add_edge("load_state", "resolve_scenario")
    graph.add_edge("resolve_scenario", "build_plan")
    graph.add_edge("build_plan", "select_capability")
    graph.add_edge("select_capability", "execute_capability")
    graph.add_edge("execute_capability", "validate_result")
    graph.add_edge("validate_result", "summarize_context")
    graph.add_edge("summarize_context", "update_memory")
    graph.add_edge("update_memory", "evaluate_sufficiency")

    graph.add_conditional_edges(
        "evaluate_sufficiency",
        route_after_sufficiency,
        {
            "compose_response": "compose_response",
            "select_capability": "select_capability",
        },
    )

    graph.add_edge("compose_response", "persist_run")
    graph.add_edge("persist_run", END)

    return graph.compile()
