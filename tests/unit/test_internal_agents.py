from orchestrator.agents.context_answer_agent import ContextAnswerAgent
from orchestrator.agents.planning_delegation_agent import PlanningDelegationAgent
from orchestrator.agents.scenario_understanding_agent import ScenarioUnderstandingAgent


def test_scenario_understanding_agent_returns_expected_fields() -> None:
    agent = ScenarioUnderstandingAgent()

    result = agent.analyze("Покажи график", attachments=[])

    assert result.intent
    assert result.scenario_hints
    assert isinstance(result.attachment_artifact_needs, list)
    assert result.normalized_task_description == "Покажи график"


def test_planning_delegation_agent_routes_by_scenario() -> None:
    agent = PlanningDelegationAgent()

    qa = agent.propose("factual_qa")
    file_mode = agent.propose("file_analysis")

    assert qa.capability_type == "qa_tool"
    assert file_mode.capability_type == "file_tool"
    assert qa.next_step == "select_capability"


def test_context_answer_agent_assembles_response_and_artifacts() -> None:
    agent = ContextAnswerAgent()
    evidence = [{"validated": True, "value": "x"}]

    result = agent.assemble("artifact_first_response", evidence)

    assert "validated_evidence=1" in result.compressed_context
    assert result.artifact_package
    assert "artifact_first_response" in result.response_assembly
